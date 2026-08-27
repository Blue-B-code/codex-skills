---
name: ticket-driver
description: Skill d'entrée pour traiter un ticket Redmine de bout en bout : retours de revue (MR GitLab / PR GitHub / journal Redmine) OU implémentation de feature, jusqu'au reporting Redmine (statut, assignataire, capture d'écran, liens PR complets) et à l'envoi en recette. 3 modes par projet (auto / propose / signal) ; routage automatique vers le skill projet (openimis-feature, mi, ...).
---

# ticket-driver

## Objectif
Traiter un ticket Redmine (fix de revue OU feature) de la prise en main jusqu'à la recette, selon le **mode** du projet (`auto`, `propose`, `signal`). Respecter la convention du projet et sa gate de validation.

## Modes (par projet, dans `state/config.json` → `projects.<name>.mode`)
- **auto** : corriger + valider + push + report + journal Redmine, sans validation humaine.
- **propose** (défaut) : **préparer la proposition** (worktree + fix + gate + `state/proposals/<projet>_<mr>.md`), **envoyer l'approbation Telegram** (2 boutons ✅/❌), **NE PAS pousser/reporter** tant que non approuvé.
- **signal** : **notifier seulement** (message info Telegram, pas de fix ni de bouton).

## Routage projet (OBLIGATOIRE — à faire en premier)
- `/home/y-note/openimis*` → skill **openimis-feature**
- `/home/y-note/OrangeMoney/MobileInvoice` → skill **mi**
- Autre → lire `CLAUDE.md` / convention du repo.

## Workflow (mode propose — cœur)
1. **Contexte** : le `fetch` détecte la revue (MR/PR/ticket) ; le retour porte `body`, `url`, `title`, `discussion_id`, `key`, `sub`, `sub_id`.
2. **`propose.py`(déterministe, rapide)** : écrit `state/proposals/<projet>_<mr>.md` (PROJECT, MR, TITLE, URL, DISCUSSION, MARK_KEY, MARK_SUB, MARK_ID, SUMMARY) et envoie l'**approbation Telegram** (`tg.py send-approval`, boutons ✅/❌). Marque l'item `proposed`. **N'implémente pas, ne pousse pas, ne reporte pas.**
3. **Approbation** (humain sur Telegram) :
   - ✅ → `scripts/ticket-driver-approve.sh <projet> <mr>` : lance `codex exec` qui **implémente** le fix (worktree de la branche source), **valide** (gate du projet), **pousse**, puis **reply + résolution + synthèse** et **journal Redmine** ; marque (mark-key). Statut `approved`.
   - ❌ → statut `rejected`, aucune action.
4. **Marquer** : `mark-key --project <p> --key <key> --sub <sub> --id <id>` (dédup).
5. **Escalade** : retour non-actionnable/ambigu/risqué → ne pas répondre/résoudre ; le résumer, le marquer comme traité.

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
