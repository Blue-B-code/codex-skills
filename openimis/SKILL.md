---
name: openimis
description: "Apply the standard git + PR workflow for a feature in OpenIMIS repos: main openIMIS (/home/y-note/openimis — frontend-packages modules and openimis-be-*_py backends: create feature-<n> from develop, commit once, push to ynote, open a PR to openimis develop with the description filled from the official openIMIS PR template) and OpenIMIS front-end modules under /home/y-note/openimis-comores and /home/y-note/openimis-csu (create feature-<n> from the correct base (develop-comores for Comores, test-csu for CSU), commit once, open the PR with the pr script, then fan out the same commit with the gff script to test-comores/main-comores for Comores or hotfix-csu/release-csu for CSU). Use when the user asks to develop an openimis feature (main repo, Comores or CSU), do 'le même travail'/'same work' in another module, or port a patch between modules."
---

# Workflow git + PR de développement de features OpenIMIS (develop, Comores & CSU)

## Objectif

> **Reporting** : si ce travail vient d'un ticket Redmine, après implémentation/PR suivre le skill **ticket-driver** pour le reporting (statut recette, assignataire, capture) et l'envoi en recette — ne pas laisser le ticket sans mise à jour.

Créer les branches et ouvrir les PR d'une feature dans un ou plusieurs modules OpenIMIS (repo principal, Comores, CSU) en suivant la procédure validée, sans redemander la marche à suivre à l'utilisateur.

## Espaces de travail et prérequis
- OpenIMIS principal : `/home/y-note/openimis`
  - Frontend : `/home/y-note/openimis/frontend-packages/<Module>` (ex. `ClaimModule`, `PaymentModule`, `LedgerModule`)
  - Backend : `/home/y-note/openimis/openimis-be-<module>_py` (ex. `openimis-be-core_py`, `openimis-be-contract_py`)
  - Assemblies exclues sauf mention explicite : `openimis-fe_js`, `openimis-be_py`, `openimis-dist_dkr`
- Comores : `/home/y-note/openimis-comores/<module>_js` (ex. `openimis-fe-contribution_js`, `openimis-fe-payment_js`)
- CSU : `/home/y-note/openimis-csu/<module>_js` (ex. `openimis-fe-claim_js`)
- Remotes : `origin` = openimis (repo de base des PR) ; `ynote` = Y-Note-SAS (fork de push, créé automatiquement par les scripts si absent)
- Scripts : `/home/y-note/mes_scripts/open-pr.sh` (alias `pr`) et `/home/y-note/mes_scripts/git-feature-fanout.sh` (alias `gff`). En shell non interactif, appeler les scripts directement (les alias viennent de `~/.bashrc`).
- `gh` doit être authentifié avec le scope `repo`.

## Validation avant fanout (obligatoire)
Avant de fanouter un changement vers les autres branches, le changement doit d'abord être **testé et validé par l'utilisateur sur une seule branche** :
- Le changement doit être implémenté, committé et testé sur une branche unique (la branche principale de la feature, ex. `feature-<n>`).
- Faire valider le résultat par l'utilisateur (revue du diff, tests, rendu, etc.) avant toute diffusion vers d'autres branches.
- Ne lancer le fanout (`gff` / cherry-pick vers les autres cibles) qu'après validation explicite de l'utilisateur.
- Ce principe s'applique à **tous** les cas de fanout : Comores (`test-comores`/`main-comores`), CSU (`hotfix-csu`/`release-csu`) et toute autre cible.

## Workflow OpenIMIS principal (develop) — 2 PRs par module

Chaque module modifié reçoit **deux PRs successives** (gitflow interne Y-Note) :

1. **PR de review** : `feature-<n>` (poussée sur `ynote`) → branche `develop` de `Y-Note-SAS/<repo>`. C'est la PR que le bot/la revue examine ; les corrections se font sur la branche de feature, dans cette même PR, jusqu'à validation.
2. **PR de publication** : branche `develop` de `Y-Note-SAS/<repo>` → branche `develop` de `openimis/<repo>`, **une fois la PR de review mergée** dans la develop du fork.

⚠️ On ne PR **jamais** directement `feature-<n>` vers `openimis:develop` (ancien flow) : la develop de ynote est le passage obligé, c'est elle qu'on merge dans openimis.

### Étapes
1. Partir de `origin/develop` à jour : `git fetch origin --prune` puis `git checkout -b feature-<n> origin/develop` (`n` = numéro de feature transmis par l'utilisateur, ex. `feature-37855`).
2. **Working tree propre obligatoire** : vérifier `git status --porcelain`. S'il y a des changements non commités, ne pas les écraser : résumer ce qu'ils contiennent (`git status`, `git diff --stat`) et demander à l'utilisateur quoi en faire (stash, commit séparé, abandon, conserver).
3. Implémenter la feature puis committer en **un seul commit** (message descriptif, ex. `add unit tests for claim pickers`).
4. Pousser vers `ynote` : `git push -u ynote feature-<n>`. Si le remote `ynote` est absent : `git remote add ynote https://github.com/Y-Note-SAS/<repo>.git`.
5. **PR 1 — vers la develop du fork (review)** : vérifier d'abord que la branche existe sur le fork (`git ls-remote --heads ynote refs/heads/develop`) ; si elle est absente, la créer depuis `origin/develop` (`git push ynote refs/remotes/origin/develop:refs/heads/develop`). Puis, description remplie depuis le template officiel openIMIS (**jamais `--fill`**) :
   - `gh pr create --repo Y-Note-SAS/<repo> --base develop --head feature-<n> --title "feature <n> — <description courte>" --body-file <fichier>`
6. Revue / corrections dans la PR 1, puis merge de `feature-<n>` dans la develop du fork (revue humaine ou bot ; ne pas merger soi-même sauf demande explicite).
7. **PR 2 — vers openimis (publication)**, seulement après le merge de la PR 1 :
   - resynchroniser le fork si sa develop est en retard sur openimis (`git fetch origin --prune` puis merger `origin/develop` dans `ynote/develop`) afin que la PR ne contienne que le travail Y-Note ;
   - `gh pr create --repo openimis/<repo> --base develop --head Y-Note-SAS:develop --title "feature <n> — <description courte>" --body-file <fichier>`
8. Vérifier les PRs ouvertes et les diffs ; rendre la main avec les liens, **présentés séparément** :

   ```
   PRs vers Ynote
   ---
   - <repo> : <lien PR 1 (feature-<n> → ynote develop)>

   PRs vers openimis
   ---
   - <repo> : <lien PR 2 (ynote develop → openimis develop)>
   ```

### Template de description de PR openIMIS (obligatoire)
Les **deux** PRs (vers la develop du fork et vers openimis) utilisent ce template, rempli honnêtement.
Remplir chaque section du template officiel (source : `openimis/.github/PULL_REQUEST_TEMPLATE.md`) :

```
#Thank you for your contribution to openIMIS!
#Please complete the sections below. Anything in comments is guidance and can be deleted.

# Description

Description claire et concise du changement : pourquoi est-il nécessaire, quel problème résout-il ?

# Type of Change

- [x] Feature
- [ ] Bug fix
- [ ] Chore (Refactor, Docs, CI/CD)
- [ ] Other, please specify

## Related Issue(s) / Task(s)
- [ ] Requires [link to github PR], [link to github PR] needs to be merged first before this one
- [ ] Relates to [link to github PR], this needs to be merged before [link to github PR]
- [x] External reference (e.g., Jira): feature <n>

## Demo

Captures d'écran / gifs / lien de démo, ou « N/A » si non applicable.

## Checklist
- [x] Unit tests added/modified
- [x] I18n / translation handled
```

Cocher les cases réellement applicables (Type of Change, Checklist) et compléter les sections honnêtement.

### Section « Related Issue(s) / Task(s) » — PR liées entre modules

Quand une feature touche plusieurs modules (plusieurs PR liées à la même feature), relier explicitement les PR entre elles, en plus de la référence externe `feature <n>` :

- **PR dépendante** (elle consomme un mécanisme/API ajouté par une autre PR, ex. un module qui utilise une nouvelle capacité de `fe-core`, ou un frontend qui consomme de nouvelles requêtes GraphQL du backend) : cocher `Requires` et lister la PR prérequise, ex. :
  `- [x] Requires [openimis/openimis-fe-core_js#348](https://github.com/openimis/openimis-fe-core_js/pull/348), needs to be merged first before this one`
- **PR prérequise / de base** (elle est consommée par d'autres PR de la même feature) : cocher `Relates to` et lister les PR qui en dépendent, ex. :
  `- [x] Relates to [openimis/openimis-fe-contribution_js#64](https://github.com/openimis/openimis-fe-contribution_js/pull/64) and [openimis/openimis-fe-payment_js#39](https://github.com/openimis/openimis-fe-payment_js/pull/39), this needs to be merged before them`
- **Frontend ↔ backend** : la PR frontend coche `Requires` avec la PR backend dont elle consomme les requêtes ; la PR backend coche `Relates to` avec la PR frontend.
- Laisser les lignes non utilisées telles quelles (placeholders d'origine) ; ne cocher que les lignes réellement remplies.

## Workflow Comores
1. `git fetch origin --prune` dans le module concerné.
2. Créer `feature-<n>` depuis `origin/develop-comores` à jour : `git checkout -b feature-<n> origin/develop-comores`.
3. Committer la modification en **un seul commit** (message descriptif, ex. `disable manual payments in family overview page`).
4. PR principale : `pr -b develop-comores -r origin` (pousse `feature-<n>` vers `ynote` et ouvre/actualise la PR vers mngoe `develop-comores`).
5. **Validation utilisateur obligatoire** : avant tout fanout, faire tester et valider le changement par l'utilisateur sur cette branche/PR principale (voir « Validation avant fanout (obligatoire) »). Ne pas continuer sans validation explicite.
6. Fanout : `gff -n 1 -r origin test-comores main-comores` → crée `feature-<n>-test-comores` et `feature-<n>-main-comores` (cherry-pick du commit), les pousse vers `ynote` et ouvre les PR vers `test-comores` et `main-comores`.
- Même numéro de feature pour tous les modules touchés (ex. `feature-37791` dans contribution ET payment).

## Workflow CSU
1. `git fetch origin --prune`.
2. Créer `feature-<n>` depuis `test-csu` : `git checkout -b feature-<n> origin/test-csu`.
3. Committer la modification en un seul commit.
4. PR principale : `pr -b test-csu -r origin`.
5. **Validation utilisateur obligatoire** : avant tout fanout, faire tester et valider le changement par l'utilisateur sur cette branche/PR principale (voir « Validation avant fanout (obligatoire) »). Ne pas continuer sans validation explicite.
6. Fanout : `gff -n 1 -r origin <cible>` où `<cible>` dépend de la typologie de déploiement :
   - `hotfix-csu` pour un correctif urgent ;
   - `release-csu` pour une fonctionnalité normale.
   Si la typologie n'est pas claire, demander à l'utilisateur.
- Nommage des branches fanout : `feature-<n>-hotfix-csu` / `feature-<n>-release-csu`.

## Pièges connus
- GitHub **refuse une PR sans commit** : la PR 2 (`ynote develop` → `openimis develop`) n'est possible qu'après le merge de la PR 1, sinon la branche de tête n'a rien de plus que la base.
- Un fork `ynote` **peut ne pas avoir de branche `develop`** (cas constaté sur `openimis-fe-policy_js`, qui n'avait que `main` et des branches de feature) : la créer depuis `origin/develop` avant d'ouvrir la PR 1.
- Une develop de fork peut être **en retard** sur `openimis/develop` (cas de `openimis-fe-contribution_plan_js` et `openimis-be-policy_py`) : la resynchroniser avant la PR 2 pour que le diff ne contienne que le travail Y-Note.
- `gff` exige un working tree propre et revient sur la branche source à la fin (trap).
- Ne pas relancer `gff` inutilement sur une branche déjà fanoutée : le script reset + re-cherry-pick (nouveaux SHAs) + force-push.
- Le script `pr` crée la PR avec `--fill` (description = liste des commits) : dans le workflow OpenIMIS principal, ne pas l'utiliser pour la description — créer la PR avec `gh pr create --body-file` rempli depuis le template openIMIS.
- L'API GitHub renvoie parfois des 503 intermittents (pas un problème d'auth : 401/403 = auth/permissions, 503 = indisponibilité serveur). Réessayer avec backoff. Si `gff` échoue seulement à l'étape création de PR (les branches sont déjà poussées sur `ynote`), créer les PR manuellement via REST :
  `gh api --method POST repos/mngoe/<repo>/pulls -f title="<titre>" -f head="Y-Note-SAS:<branche>" -f base="<base>"` (avec retry + sleep).
- Après exécution : vérifier les PR ouvertes (`gh pr list --repo mngoe/<repo> --state open`) et le diff avant de rendre la main ; résumer avec les liens des PR.
