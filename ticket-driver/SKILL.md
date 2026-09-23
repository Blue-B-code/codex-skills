---
name: ticket-driver
description: Skill d'entrée pour traiter un ticket Redmine de bout en bout : retours de revue (MR GitLab / PR GitHub / journal Redmine) OU implémentation de feature, jusqu'au reporting Redmine (statut, assignataire, capture d'écran, liens PR complets) et à l'envoi en recette. Inclut la validation des findings du bot collés depuis Slack (tableau 4 colonnes Sévérité/Finding/Bouton/Pourquoi + bouton Pertinent ou Faux positif à cliquer). 3 modes par projet (auto / propose / signal) ; routage automatique vers le skill projet (openimis, mi, ...).
---

# ticket-driver

## Objectif
Traiter un ticket Redmine (fix de revue OU feature) de la prise en main jusqu'à la recette, selon le **mode** du projet (`auto`, `propose`, `signal`). Respecter la convention du projet et sa gate de validation.

## Modes (par projet, dans `state/config.json` → `projects.<name>.mode`)
- **auto** : corriger + valider + push + report + journal Redmine, sans validation humaine.
- **propose** (défaut) : **préparer la proposition** (worktree + fix + gate + `state/proposals/<projet>_<mr>.md`), **envoyer l'approbation Telegram** (2 boutons ✅/❌), **NE PAS pousser/reporter** tant que non approuvé.
- **signal** : **notifier seulement** (message info Telegram, pas de fix ni de bouton).

## Routage projet (OBLIGATOIRE — à faire en premier)
- `/home/y-note/openimis*` → skill **openimis**
- `/home/y-note/OrangeMoney/MobileInvoice` → skill **mi**
- `/home/y-note/flownote` → skill **flownote**
- Autre → lire `CLAUDE.md` / convention du repo.

## Workflow (mode propose — cœur)
1. **Contexte** : le `fetch` détecte la revue (MR/PR/ticket) ; le retour porte `body`, `url`, `title`, `discussion_id`, `key`, `sub`, `sub_id`.
2. **`propose.py`(déterministe, rapide)** : écrit `state/proposals/<projet>_<mr>.md` (PROJECT, MR, TITLE, URL, DISCUSSION, MARK_KEY, MARK_SUB, MARK_ID, SUMMARY) et envoie l'**approbation Telegram** (`tg.py send-approval`, boutons ✅/❌). Marque l'item `proposed`. **N'implémente pas, ne pousse pas, ne reporte pas.**
3. **Approbation** (humain sur Telegram) :
   - ✅ → `scripts/ticket-driver-approve.sh <projet> <mr>` : lance `codex exec` qui **implémente** le fix (worktree de la branche source), **valide** (gate du projet), **pousse**, puis **reply + résolution + synthèse** et **journal Redmine** ; marque (mark-key). Statut `approved`.
   - ❌ → statut `rejected`, aucune action.
4. **Marquer** : `mark-key --project <p> --key <key> --sub <sub> --id <id>` (dédup).
5. **Escalade** : retour non-actionnable/ambigu/risqué → ne pas répondre/résoudre ; le résumer, le marquer comme traité.

## Findings de revue (bot automatique ou reviewer) — OBLIGATOIRE
Dès qu'une PR/MR porte des findings de revue (résumé du bot + commentaires ligne à ligne) :
1. **Lister tous les findings** (commentaires de la PR/MR et commentaires de revue attachés à un fichier/une ligne).
2. **Traiter seulement les pertinents** (bug réel, régression, non-conformité au contrat, sécurité) : correction sur la branche de la PR/MR, gate de validation du skill projet, push sur la même branche, jamais de nouvelle branche.
3. **Pour chaque finding non pertinent : répondre dans la PR/MR en une phrase très courte** donnant la raison (convention du core, comportement voulu, pattern déjà utilisé ailleurs, cas impossible, hors périmètre du module…). Répondre **en fil** quand le finding est un commentaire de revue (`pulls/<n>/comments/<id>/replies`), sinon en commentaire de la PR/MR.
4. **Une phrase, pas plus** : pas de justification détaillée, pas de débat avec le bot.
5. **Aucun finding sans suite** : soit corrigé, soit répondu brièvement. Boucler jusqu'à ce qu'il ne reste que des faux positifs / non pertinents (vérifier après chaque push : le bot re-poste des findings).

### Findings collés depuis Slack (feedback bot)
Quand l'utilisateur colle une notification Slack de findings et demande de les valider :
1. **Vérifier avant de classer** : confronter chaque finding au code réel (fichier + ligne), aux tests présents et à la convention du module/framework — ne jamais se fier à l'énoncé du bot.
2. **Traiter d'abord les valides** (correctif + tests, push sur la branche de la PR, CI verte), répondre en **une phrase** aux non pertinents ; puis seulement classer.
3. **Rendre le tableau de validation**, dans l'**ordre exact du message Slack**, avec **au plus 4 colonnes** : `Sévérité | Finding | Bouton | Pourquoi`.
   - `Bouton` = ce que l'utilisateur clique dans Slack : **Pertinent** ou **Faux positif**.
   - `Pourquoi` = une clause très courte (test existant, convention du core, faux positif factuel, hash du correctif).
4. **Mapping** : valide/traité → *Pertinent* ; faux positif factuel → *Faux positif* ; vrai mais non applicable (convention, choix assumé, hors périmètre) → *Faux positif* en le précisant dans `Pourquoi`.
5. Recopier aussi la classification dans `state/findings/<projet>_<pr>.md` (trace + feedback bot).
6. Motifs récurrents (faux positifs et vrais findings), commandes GitHub et exemple : `references/slack-findings-validation.md`.

## Fichiers d'état
- `state/projects.json` : curseurs des notes/journaux traités (dédup).
- `state/approvals.json` : statut `proposed`/`approved`/`rejected`/`signaled` par item.
- `state/proposals/<projet>_<mr>.md` : proposition en attente d'approbation.

## Commandes utiles
- Fetch : `scripts/rfbot.py fetch --project <p> --out /tmp/items.json --pretty`
- Telegram : `scripts/tg.py send-approval|send-info|poll`
- Approbation : `scripts/ticket-driver-approve.sh <projet> <mr>`
- Report : `scripts/rfbot.py report --project <p> --target <mr:33|ticket:37862> --action <reply|resolve|summary|journal>`
- Modes : `scripts/rfbot.py modes` (lister) ; `scripts/rfbot.py set-mode --project <p> --mode <auto|propose|signal>` (changer).
- Config : `state/config.json` (`projects.<name>.mode`, `telegram.*`, `redmine.*`).


## Sprint (nouveaux tickets Redmine assignés)
- **Détection** : `rfbot.py fetch` ajoute une source `sprint_ticket` : version **sprint courant** = `DH-OpenIMIS<AAAA><MM><NN>` **ouverte** avec la `due_date` la plus proche ≥ aujourd'hui (dédupliquée par `version.id`), puis issues `assigned_to_id=redmine.me_id` dans cette version (projets routés via `redmine.sprint_routes` : `199→openimis`, `170→mi`, `209→flownote`).
- **Item** : `kind=sprint_ticket`, `key=sprint_ticket_<id>`, `sub=processed_tickets`, `sub_id=ticket_id`, portant `subject`, `body`, `tracker`, `url`, `redmine_project_id`.
- **Propose** : pour un `sprint_ticket`, le modèle rédige un **plan d'implémentation clair** (contexte, étapes, fichiers, PR attendue, tests) et l'envoie sur Telegram ; la proposition est écrite dans `state/proposals/<projet>_<ticket_id>.md`.
- **Approbation** : ✅ → le skill projet implémente la feature (worktree `feature-<n>`, validation, push, PR, journal Redmine recette) ; ❌ → rejeté.

## Validation
- La gate de validation est celle du **skill projet** (`mi` / `openimis` / `flownote`) : lire ce skill et appliquer **sa** validation (tests unitaires + build du module/module openIMIS, conteneur MI, uv/pytest flownote…).
- **Ciblée** : n'exécuter que les tests/analyses des **fichiers touchés** ; ne pas lancer la suite complète (ex. pas de `phing full-build`). Les commandes sont dans `state/config.json` → `projects.<name>.validation`.
- **Fail-fast** : `timeout` global (`validation.timeout_seconds`, défaut 900 s). Si l'environnement est cassé (conteneur instable, donnée DB absente), **rapporter la cause exacte et s'arrêter** — pas de retry, pas de hang, pas de push en masse.
- Vérifier aussi la **CI de la PR** (ex. workflow `vitest`) après chaque push : un finding « tests absents » est souvent un faux positif lié au seul dernier commit, la CI verte le prouve.
