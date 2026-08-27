---
name: mi
description: "Projet MI (MobileInvoice, Orange Money, PayNote / Y-Note) : stack locale Docker, branche de démarrage develop-sp-local, validation obligatoire du code dans le conteneur orangemoney_web-mi (PHPUnit, Vitest, phpcs, phpstan, phpmd, eslint-vite, tsc, jscpd), et tests fonctionnels UILicious (manifeste ci/uilicious-tests.json, exécution via uilicious-cli sur le projet Paynote-MI). À utiliser pour tout travail sur /home/y-note/OrangeMoney/MobileInvoice : diagnostiquer la stack locale, valider du code PHP/TS/React, ou ajouter/fixer/valider des tests fonctionnels UILicious."
---

# Projet MI (MobileInvoice) — stack locale, validation QA et tests fonctionnels

> **Reporting** : si ce travail vient d'un ticket Redmine, après implémentation/PR suivre le skill **ticket-driver** pour le reporting (statut recette, assignataire, capture) et l'envoi en recette.


## Stack locale MI (Docker)

- Repo : `/home/y-note/OrangeMoney/MobileInvoice` (le code est monté dans le conteneur `orangemoney_web-mi` sous `/var/www/mobileinvoice`).
- Conteneurs de la stack : `nginx-test` (sert l'application : nginx + fastcgi vers `web-test`), `orangemoney_web-mi` (php-fpm, `web-test`), `cron-test`, `dynamodb-local`, `orangemoney_db-mi`, `maildev_docker_symfony--mi` (capture les emails envoyés par l'app), `phpmyadmin_orangemoney-mi`.
- L'application locale est accessible via `nginx-test` (port 80 interne, réseau docker `mi-Symfony-net`). **Ne pas lancer de serveur PHP manuel** (`php -S`) : la stack fournit déjà l'app.
- Commandes utiles :
  - `docker ps` / `docker logs <conteneur>` pour l'état.
  - Depuis `orangemoney_web-mi` : `curl http://nginx-test/fr/` pour vérifier que l'app répond.

## Branche de démarrage (`develop-sp-local`)

- La branche **`develop-sp-local`** est nécessaire pour **démarrer** la stack locale (par ex. après un redémarrage de la machine).
- Une fois la stack démarrée, elle reflète les changements de **n'importe quelle branche** sur laquelle on checkout ensuite.
- Symptôme de problème : `nginx-test` en `Restarting`, `orangemoney_web-mi` qui redémarre/plante, l'app ne répond plus (`000`/connexion refusée). Cause : la stack a été démarrée sur une mauvaise branche, ou un checkout a eu lieu pendant son fonctionnement.
- Correction :
  1. Working tree propre : `git status --porcelain` ; si des changements non commités existent, ne pas les écraser (stash ou accord utilisateur).
  2. `git checkout develop-sp-local`
  3. `docker compose -f docker-compose-test.yml up -d`
  4. Attendre que `web-test` soit healthy (healthcheck, `start_period` 600 s) puis vérifier `curl http://nginx-test/fr/` → 200.

## Validation du code (obligatoire, dans le conteneur)

Toute validation se fait **dans le conteneur `orangemoney_web-mi`** (le code local est monté dans `/var/www/mobileinvoice`), jamais sur la machine hôte.

- Tests unitaires PHP : `vendor/bin/phing -buildfile build.xml full-build` (lint, phploc, pdepend, phpmd-ci, phpcs-ci, phpcpd-ci, phpunit).
- QA PHP : `vendor/bin/phing sast-analysis` (phpstan, psalm) ; rapports dans `build/logs/` (phpstan.xml, phpcs.xml, junit).
- Tests unitaires Vite : `cd vite-frontend && npm run test:coverage` ; ciblé : `npx vitest run <fichiers>`.
- QA Vite : `npm run lint:quality` (eslint), `npx tsc --noEmit` (types), `npm run duplication` (jscpd).
- **Ciblage (à faire)** : la validation/QA doit porter en priorité sur **le code ajouté ou modifié** — exécuter le test unitaire PHP du contrôleur/service touché (`vendor/bin/phpunit --filter <Classe>`), `phpcs`/`phpstan` sur ces fichiers PHP ; pour le frontend, `npx vitest run <fichiers-touchés>`, `tsc` et `lint` sur les fichiers TS/React touchés. Ne jamais conclure « propre » si le code modifié n'a pas été couvert par ces checks.
- **Exigence** : tout doit être propre pour le code ajouté. Si des faux positifs sont détectés (warnings/erreurs pré-existants, limites de config, etc.), **les remonter à l'utilisateur avec explications** pour qu'il prenne la décision — ne pas tricher, masquer ou contourner.

## Tests fonctionnels UILicious

- Sources : `tests/functional/uilicious/` (format script UILicious : `I.goTo`, `I.fill`, `I.click`, `I.see`, `I.select`, `I.scrollToBottom`, `TEST.run(...)`, `SAMPLE.*`, `DATA.*`).
- Manifeste : `ci/uilicious-tests.json` (groupes de tests exécutés dans l'ordre sur un même worker ; le pipeline répartit les groupes entre workers).
- Exécution CI : stage « UI-Licious Tests » du `jenkinsfile-dev` → `uilicious-cli run "Paynote-MI" <path> --key <ACCESS_KEY>` ; rapports JSON dans `reports/ui-licious/` puis JUnit (`reports/uilicious-junit.xml`).
- Synchronisation cloud : `ci/upload-uilicious-tests.sh` (git = source de vérité, pousse les tests vers le projet cloud « Paynote-MI »).
- **Règles** :
  - Si un test fonctionnel n'existe pas pour une fonctionnalité : l'ajouter **et le faire valider** (exécution réelle).
  - Si un test fonctionnel est cassé : le fixer **et le faire valider**.
  - Validation locale possible (sans déployer sur mitest) : tunnel `cloudflared tunnel --url http://nginx-test` puis `uilicious-cli run "Paynote-MI" "<path>" --key <KEY> --dataObject '{"url":"https://<tunnel>.trycloudflare.com"}'` ; les tests utilisent `I.goTo((DATA.url || "https://mitest.ynote.africa") + "/fr/")` pour être paramétrables et rétro-compatibles CI.
  - La clé UILicious est fournie par l'utilisateur (ne jamais la committer ni la stocker dans le repo).
