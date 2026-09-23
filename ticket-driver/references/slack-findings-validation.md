# Validation des findings Slack (feedback bot)

## Quand
L'utilisateur colle une notification Slack (un ou plusieurs blocs : résumé de revue + findings avec pastille de sévérité) et demande de **valider les findings**.

## Sortie attendue
Un tableau **sans ordre autre que celui du message Slack**, **4 colonnes au maximum** :

| Sévérité | Finding | Bouton | Pourquoi |
|---|---|---|---|
| 🔴 Élevée | Résumé en une ligne du finding | **Pertinent** / **Faux positif** | Une clause très courte |

- `Sévérité` : pastille du message (🔴 / 🟠 / 🟢), sinon « — ».
- `Finding` : une ligne, en reprenant les mots-clés du bot (fichier + symbole).
- `Bouton` : **Pertinent** (finding réel → traité) ou **Faux positif** (à ne plus remonter).
- `Pourquoi` : la preuve, pas un avis — nom du test existant, convention du framework, garde dans le core, hash du commit du correctif.
- Les paragraphes de synthèse du message qui ne portent pas de finding (« aucun problème détecté ») se traitent par une ligne « rien à cliquer ».

## Mapping bouton
| Constat | Bouton |
|---|---|
| Bug / régression / garde manquante / test réellement absent | **Pertinent** (après correctif + test, CI verte) |
| Énoncé factuellement faux (le code fait déjà l'inverse, le test existe…) | **Faux positif** |
| Vrai mais non applicable (convention du projet, choix assumé, hors périmètre) | **Faux positif**, en le précisant dans `Pourquoi` |

## Méthode (dans cet ordre)
1. **Vérifier** chaque finding dans le code (fichier + ligne cités), dans les tests présents et dans la convention du module — ne pas croire l'énoncé du bot.
2. **Traiter** les findings valides : correctif + tests sur la **branche de la PR**, gate du skill projet, push, CI verte.
3. **Répondre en une phrase** (en fil pour un commentaire de revue) aux non pertinents.
4. **Classer** (tableau ci-dessus) et écrire la même chose dans `state/findings/<projet>_<pr>.md`.
5. **Boucler** : après un push, le bot re-poste une revue — relire, traiter, répondre, re-classer, jusqu'à n'avoir plus que des faux positifs / non pertinents.

## Motifs récurrents — à vérifier avant de classer

### Faux positifs fréquents
- **« Aucun test unitaire dans ce diff »** alors que les tests sont dans `tests/` (le bot analyse souvent le **dernier commit** seulement) → vérifier `git log --oneline <base>..HEAD` et la CI `vitest` ; mettre code **et** tests dans le **même commit** évite la plupart de ces faux positifs.
- **« `meta` en chaîne / reducer stocke null »** : vérifier l'appelant réel (`mapDispatchToProps`) et non le test.
- **Injection GraphQL via `params.join`** : convention openIMIS (`formatPageQueryWithCount`), valeurs = UUID internes.
- **`__dirname` non défini en ESM** : faux si `package.json` n'a pas `type: module` (config chargée en CJS) — la CI le prouve.
- **`Grid size` non supporté (MUI v5)** : faux en MUI v7 (Grid v2, `size` est l'API correcte).
- **Clé d'index dans le mock `Table`**, **mocks MUI partiels**, **`npm ci --legacy-peer-deps`** : mock/CI de test, aucun impact production.
- **« `PagedDataHandler.query()` envoie une requête sans filtre »** : faux, `query()` sort tôt quand `queryPrms()` est null (core).
- **« `parseData` peut renvoyer `undefined` »** : faux, il renvoie `[]` (core).
- **Filtrage métier fait côté backend** (ex. factures à charge de l'assuré) : le front n'envoie que la clé métier, le filtre + le test sont dans la PR backend.

### Findings souvent valides
- Clé de requête **stockée mais jamais comparée** → réponses obsolètes d'une requête dépassée (ajouter une garde en SUCCESS/ERROR + test).
- Données de l'ancien contexte **(totaux, listes) conservées pendant le chargement** du nouveau → réinitialiser au REQUEST + test.
- Garde manquante dans un **nouveau** code (retour anticipé, `undefined`, index hors bornes).
- **Test conditionnel incomplet** : « masqué uniquement si la valeur vaut X » → ajouter le cas valeur inattendue.
- Test qui **valide un comportement erroné** (assertion sur l'ancien contexte) → réécrire avec un vrai changement de props (`rerender`).

## Commandes utiles (GitHub)
```bash
# liste des commentaires (revue = corps, inline = fichier:ligne)
gh api repos/<owner>/<repo>/issues/<n>/comments?per_page=100
gh api repos/<owner>/<repo>/pulls/<n>/comments?per_page=100

# reponses en fil / commentaire simple
gh api --method POST repos/<owner>/<repo>/pulls/<n>/comments/<id>/replies -f body="..."
gh api --method POST repos/<owner>/<repo>/issues/<n>/comments -f body="..."

# etat de la CI
gh api repos/<owner>/<repo>/commits/<sha>/check-runs --jq '.check_runs[] | "\(.name)=\(.status)/\(.conclusion)"'
```
Astuce : `gh` installé en snap ne lit pas `/tmp` → écrire les corps de PR dans `$HOME`.

## Exemple (PR invoice, 23/09)
| Sévérité | Finding | Bouton | Pourquoi |
|---|---|---|---|
| 🟠 Moyenne | `paramsKey` stocké mais jamais comparé → réponse tardive d'une ancienne famille | **Pertinent** | Garde `isStaleResponse` ajoutée en SUCCESS/ERROR + test (commit `6e5db6b`) |
| 🟠 Moyenne | Pas de garde anti-réponse obsolète pour l'overview | **Pertinent** | Clé dérivée des params + test (`6e5db6b`) |
| 🟢 Faible | Totaux de la famille précédente visibles pendant le chargement | **Pertinent** | Remis à zéro au REQUEST + test (`6e5db6b`) |
| 🔴 Élevée | Injection GraphQL via `params.join` | **Faux positif** | Convention openIMIS, valeurs = UUID internes |
| 🟠 Moyenne | Composant/actions sans tests | **Faux positif** | Tests présents (`tests/components/…` 22 tests, `tests/actions.test.js` 7 tests) |
| 🟠 Moyenne | Nouveaux cas du reducer sans tests | **Faux positif** | `tests/reducer.test.js` (16 tests) |
| 🔴 Élevée | `meta` chaîne → le reducer stocke `null` | **Faux positif** | Le composant passe `{ paramsKey }` ; seul le test était ambigu (corrigé) |
| 🟠 Moyenne | Pas de filtre de responsabilité (AFD/gouvernement) | **Faux positif** | Filtrage backend `thirdparty_type=insuree` + test `be-invoice_py#48` |
