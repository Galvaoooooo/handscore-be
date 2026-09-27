"""
Scraper générique pour clubee.com — pilote par competitions.json.

Pour AJOUTER une compétition ou une division : n'ouvre pas ce fichier,
édite competitions.json (voir son champ "_comment"). Ce script lit ce
fichier et scrape automatiquement tout ce qui y est listé.

Usage :
    pip install requests beautifulsoup4
    python scraper.py

Sortie :
    data/manifest.json          -> liste des compétitions/divisions (pour le menu)
    data/<division_key>.json    -> matchs + classement de cette division
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "fr-BE,fr;q=0.9,en;q=0.8",
}
REQUEST_DELAY = 1.0
DATA_DIR = Path("data")

# Palette de couleurs assignée automatiquement aux équipes, dans l'ordre
# où elles apparaissent (pas besoin de les définir à la main).
PALETTE = ["#FF6B6B", "#FFC93C", "#4D9DFF", "#17E3A6", "#FF9F4D",
           "#B98CFF", "#2FD4C8", "#6C7BFF", "#FF4F81", "#8A93A6",
           "#5CD6E8", "#E8C15C"]


@dataclass
class Match:
    gameday: int
    game_id: int
    home: str
    away: str
    date: str
    time: Optional[str]
    home_score: Optional[int]
    away_score: Optional[int]
    status: str  # 'FT' | 'LIVE' | 'SCHED' | 'CANC'


def team_code(name: str) -> str:
    words = [w.strip(".") for w in name.split() if w.strip(".").isalpha()]
    if len(words) >= 2:
        return "".join(w[0] for w in words[:3]).upper()
    return (name[:3] or "TBD").upper()


def clean_team_name(raw: str) -> str:
    # Enlève le suffixe catégorie Clubee, ex "Derdaele Sp. Pelt D1 M (Senior M)"
    return re.sub(r"\s*D\d+\s*[A-Z]{0,2}\s*\d*\s*\(.*?\)\s*$", "", raw).strip()


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return BeautifulSoup(resp.text, "html.parser")


_GAMEDAY_RE = re.compile(r"Gameday\s+(\d+)", re.IGNORECASE)

# Ordre important : on teste les motifs les plus spécifiques d'abord.
_PAT_CANC = re.compile(r"^(?P<home>.*?)-\s*:\s*-Cancelled(?P<away>.*)$")
_PAT_LIVE = re.compile(r"^(?P<home>.*?)(?P<time>\d{1,2}:\d{2})(?P<date>\d{2}\.\d{2}\.\d{4})Live(?P<away>.*)$")
_PAT_FT   = re.compile(r"^(?P<home>.*?)(?P<hs>\d{1,3})\s*-\s*(?P<as>\d{1,3})(?P<date>\d{2}\.\d{2}\.\d{4})(?P<away>.*)$")
_PAT_SCHED= re.compile(r"^(?P<home>.*?)(?P<time>\d{1,2}:\d{2})(?P<date>\d{2}\.\d{2}\.\d{4})(?P<away>.*)$")


def parse_match_link(a_tag, gameday: int) -> Optional[Match]:
    href = a_tag.get("href", "")
    m_id = re.search(r"/games/(\d+)", href)
    if not m_id:
        return None
    text = a_tag.get_text(separator="", strip=True)
    gid = int(m_id.group(1))

    m = _PAT_CANC.match(text)
    if m:
        return Match(gameday, gid, clean_team_name(m["home"]), clean_team_name(m["away"]),
                     "", None, None, None, "CANC")

    m = _PAT_LIVE.match(text)
    if m:
        return Match(gameday, gid, clean_team_name(m["home"]), clean_team_name(m["away"]),
                     m["date"], m["time"], None, None, "LIVE")

    m = _PAT_FT.match(text)
    if m:
        return Match(gameday, gid, clean_team_name(m["home"]), clean_team_name(m["away"]),
                     m["date"], None, int(m["hs"]), int(m["as"]), "FT")

    m = _PAT_SCHED.match(text)
    if m:
        return Match(gameday, gid, clean_team_name(m["home"]), clean_team_name(m["away"]),
                     m["date"], m["time"], None, None, "SCHED")

    return None


def scrape_division(site: str, league_id: int, season_id: int) -> tuple[list[Match], list[dict]]:
    base = f"https://www.clubee.com/{site}"

    # --- résultats + calendrier (une seule page pour toute la saison) ---
    results_url = f"{base}/games-371075v4/leagues/{league_id}/seasons/{season_id}"
    soup = get_soup(results_url)

    matches: list[Match] = []
    current_gameday = 0
    for el in soup.find_all(True):
        txt = el.get_text(strip=True)
        gd_match = _GAMEDAY_RE.search(txt) if el.name in ("h1", "h2", "h3", "h4", "div", "span") else None
        if gd_match and len(txt) < 20:
            current_gameday = int(gd_match.group(1))
            continue
        if el.name == "a" and "/games/" in el.get("href", ""):
            m = parse_match_link(el, current_gameday or 0)
            if m:
                matches.append(m)

    seen = set()
    unique_matches = [m for m in matches if not (m.game_id in seen or seen.add(m.game_id))]

    # --- classement ---
    standings_url = f"{base}/standings-371073v4/leagues/{league_id}/seasons/{season_id}"
    soup2 = get_soup(standings_url)
    table = soup2.find("table")
    standings: list[dict] = []
    if table:
        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 9:
                continue
            standings.append({
                "club": clean_team_name(cells[1]),
                "mj": int(cells[2]), "v": int(cells[3]), "n": int(cells[4]), "d": int(cells[5]),
                "gs": int(cells[6]), "ga": int(cells[7]),
                "pts": int(re.sub(r"\D", "", cells[9])) if len(cells) > 9 else 0,
            })

    return unique_matches, standings


def build_division(site: str, league_id: int, season_id: int) -> dict:
    matches, standings = scrape_division(site, league_id, season_id)

    # équipes -> code + couleur, assignés automatiquement et de façon stable
    team_names = []
    for m in matches:
        for n in (m.home, m.away):
            if n not in team_names:
                team_names.append(n)
    codes: dict[str, str] = {}
    used_codes = set()
    for name in team_names:
        code = team_code(name)
        base_code = code
        i = 2
        while code in used_codes:
            code = f"{base_code}{i}"
            i += 1
        used_codes.add(code)
        codes[name] = code
    teams = {codes[n]: {"n": n, "c": PALETTE[i % len(PALETTE)]} for i, n in enumerate(team_names)}

    by_gameday: dict[int, list] = {}
    for m in matches:
        by_gameday.setdefault(m.gameday, []).append([
            codes[m.home], codes[m.away], m.home_score, m.away_score, m.date, m.time, m.status
        ])

    standings_rows = [
        [codes.get(s["club"], team_code(s["club"])), s["mj"], s["v"], s["n"], s["d"], s["gs"], s["ga"], s["pts"]]
        for s in standings
    ]

    return {
        "teams": teams,
        "gamedays": [by_gameday[g] for g in sorted(by_gameday)],
        "standings": standings_rows,
    }


def main():
    config = json.loads(Path("competitions.json").read_text(encoding="utf-8"))
    DATA_DIR.mkdir(exist_ok=True)

    manifest = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "competitions": []}

    for comp in config["competitions"]:
        comp_entry = {"key": comp["key"], "label": comp["label"], "divisions": []}
        for div in comp["divisions"]:
            print(f"Scraping {comp['label']} / {div['label']}...")
            try:
                data = build_division(comp["site"], div["league_id"], div["season_id"])
                data["label"] = div["label"]
                data["qual_zone"] = div.get("qual_zone", 0)
                (DATA_DIR / f"{div['key']}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                comp_entry["divisions"].append({"key": div["key"], "label": div["label"]})
                print(f"  OK -> data/{div['key']}.json")
            except Exception as e:
                print(f"  ECHEC pour {div['label']} : {e}")
        manifest["competitions"].append(comp_entry)

    (DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Terminé -> data/manifest.json")


if __name__ == "__main__":
    main()
