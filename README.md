# HandScore BE

Appli de résultats/classements pour le handball belge (URBH-KBHB), inspirée de Flashscore.

## Comment ça marche

- `competitions.json` : la config. **C'est le seul fichier à modifier pour ajouter une compétition ou une division.**
- `scraper.py` : va chercher les résultats, le calendrier et le classement sur clubee.com pour chaque division listée dans `competitions.json`, et écrit le résultat dans `data/`.
- `index.html` : le site. Il lit les fichiers dans `data/` et les affiche.
- `.github/workflows/scrape.yml` : automatise tout ça (relance le scraper régulièrement, republie le site).

## Ajouter une nouvelle division

1. Trouve la page "Results" de la division sur clubee.com. L'URL ressemble à :
   `https://www.clubee.com/handballbelgium/xxx/leagues/18702/seasons/220`
2. Note les deux nombres : `league_id` (ici 18702) et `season_id` (ici 220).
3. Ouvre `competitions.json` sur GitHub (bouton crayon ✏️ pour éditer) et ajoute une ligne dans le tableau `divisions`, sur le modèle des autres.
4. Committe le changement. Le site se remet à jour automatiquement (le workflow tourne à chaque modification, et régulièrement le weekend).

## Ajouter une nouvelle compétition (pas juste une division)

Ajoute un nouvel objet dans le tableau `competitions`, avec sa propre clé (`key`), son `label`, son `site` (le nom qui apparaît dans l'URL clubee juste après clubee.com/, ex. `handballbelgium`) et son tableau `divisions`.

## Lancer le scraper toi-même en local (optionnel, pour tester)

```
pip install requests beautifulsoup4
python scraper.py
```

Ça crée/actualise les fichiers dans `data/`.
