---
name: mi
description: "Projet MI (MobileInvoice, Orange Money, PayNote / Y-Note) : workflow git (feature → develop-sp), validation obligatoire avec les commandes exactes de la CI dans le conteneur orangemoney_web-mi (phing, Vitest, eslint, tsc, jscpd), régressions de quality gates et tests fonctionnels UILicious. À utiliser pour tout travail sur /home/y-note/OrangeMoney/MobileInvoice."
---

# Projet MI (MobileInvoice) — workflow, validation, tests

> **Reporting** : si le travail vient d'un ticket Redmine, suivre le skill **ticket-driver** pour le
> reporting (statut, assignataire, capture, envoi en recette).

## Workflow git

- Une `feature-*` part de `develop` et ne merge que `develop` — **jamais `develop-sp`** (c'est un
  puits : elle reçoit des merges, elle n'en alimente aucune).
- `develop-sp` est **la seule branche d'intégration** : on y merge les features terminées (conflits
  résolus, validation relancée) et on la pousse. Jenkins la builde en continu.
- Déploiement : `DEPLOY_ACTION=Deploy` + `BRANCH_ENVIRONMENT=develop-sp` + `BRANCH_STACK=true`.
  L'instance porte plusieurs tickets à la fois → la testeuse recette en une passe.
- Une feature ne dépend jamais d'une autre : si du code commun (socle, helpers) naît dans une feature,
  on le recopie **à l'identique** dans les autres features en cours (merges sans conflit, chaque
  branche reste testable). Le partage durable passe par `develop`.
- Jamais de force-push sur `develop-sp` : si elle a divergé, on merge.

## Validation — commandes exactes de la CI, dans le conteneur

Le code local est monté dans `orangemoney_web-mi` sous `/var/www/mobileinvoice`. **Jamais de
validation sur l'hôte** (dépendances différentes) ni de commande approximative : ce sont ces
commandes-là que la CI exécute.

```bash
# PHP — stages « Phing full-build » + « SAST »
docker exec -u www-data -e HOME=/tmp -w /var/www/mobileinvoice orangemoney_web-mi \
  bash -c "vendor/bin/phing -buildfile build.xml full-build && vendor/bin/phing sast-analysis"

# Tests front — stage « JS Unit Tests »
docker exec -u www-data -e HOME=/tmp -w /var/www/mobileinvoice/vite-frontend orangemoney_web-mi \
  bash -c "npm run test:coverage"

# Qualité front — stage « JS Quality Analysis »
docker exec -u www-data -e HOME=/tmp -w /var/www/mobileinvoice/vite-frontend orangemoney_web-mi \
  bash -c "npx eslint src --ext .ts,.tsx -f checkstyle -o ../build/logs/eslint-vite.xml; npx tsc --noEmit; npx jscpd src --threshold 0 --min-tokens 50 --reporters json,xml --output ../build/logs/jscpd-vite/"
```

- Cibler d'abord le code touché (`vendor/bin/phpunit --filter <Classe>`, `npx vitest run <fichier>`),
  puis les commandes complètes ci-dessus avant de pousser.
- Ne jamais conclure « propre » sans avoir couvert le code modifié ; ne jamais désactiver, masquer ou
  contourner une règle. Un faux positif se remonte à l'utilisateur, il tranche.

## Régressions de quality gates

Quand le build annonce `X > Y (was Y)` :

1. Comparer le rapport du build fautif avec le précédent (archivés par le job) et agréger par
   `(fichier, règle)` — les numéros de ligne bougent, ils ne sont pas fiables. Pour jscpd, comparer
   les **paires de fichiers** avec le rapport de `develop`.
2. Corriger sur la branche `feature-*` qui a introduit la violation, puis la merger dans `develop-sp`.
3. Ne jamais baisser un seuil ni exclure des fichiers : le correctif est du code (helper partagé,
   import explicite, `@SuppressWarnings` ciblé et justifié).
4. Relancer le build et vérifier `Checking Regression vs Previous Build` : `✅ (unchanged)` ou mieux.

## Faut-il relancer un build ?

`DEPLOY_ACTION=Build` (tests + qualité) ≈ 15 min ; un `Deploy` complet ≈ 45-50 min.

- **Pas de build** quand les seuls changements viennent de `develop` (déjà vert) **et** que les
  compteurs du merge, mesurés en local, ne dépassent pas le dernier build vert.
- **Build nécessaire** dès qu'on ajoute/modifie du code à nous ou qu'un compteur augmente (la
  couverture, le nombre de tests et gitleaks ne se déduisent pas des compteurs locaux).

## Tests fonctionnels UILicious

- Les exécuter sur **https://develop-sp.mitest.ynote.africa/** (ou l'URL précisée dans la demande).
  Scripts : `tests/functional/uilicious/`, manifeste `ci/uilicious-tests.json`.
- Un test fonctionnel manquant pour une fonctionnalité s'ajoute **et se fait valider** ; un test cassé
  se corrige **et se fait valider**.
- La clé UILicious est fournie par l'utilisateur (variable `UILICIOUS_ACCESSKEY`) : jamais commitée.

## Stack locale

- `docker compose -f docker-compose-test.yml up -d` depuis **n'importe quelle branche** (après le
  correctif local `SKIP_DEPS_INSTALL` + `nginx.local.conf` ; en attendant, démarrer depuis
  `develop-sp-local`).
- App servie par `nginx-test` : vérifier avec `curl http://nginx-test/fr/` → 200. Ne pas lancer de
  serveur PHP manuel.
- Conteneur de travail : `orangemoney_web-mi` (php-fpm) ; état : `docker ps`, `docker logs <conteneur>`.
