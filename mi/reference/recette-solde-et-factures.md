# Recette : factures en « payé » & solde d'une entreprise

Deux tâches, une seule mécanique : la commande SQL est écrite **en clair dans
`MobileInvoice/conf/entrypoint-cron.sh`** (bloc dédié, avant le démarrage de supervisor). Elle
s'exécute au démarrage du conteneur CRON — donc à **chaque déploiement** — et **jamais en
production** (garde `APP_ENV != prod`).

## Entrées à demander avant de coder

| Tâche | Entrées |
|---|---|
| Factures en « payé » | **branche** à modifier + **ids des factures** |
| Solde d'une entreprise | **branche** + **id company** + **id méthode de paiement** + **montant** |

- Statuts de facture : `0` brouillon · `1` en cours (= à payer, seul état où la page de paiement
  publique est servie) · `2` **payé** · `-1` annulé. Par convention on demande le statut **2**.
- Méthodes de paiement : `1` OrangeMoney · `5` MTN · `6` Deposit · `7` Paynote OM · `8` M2U.
- On travaille sur **la branche fournie**, qui n'est pas toujours la nôtre : **ne jamais réécrire
  son historique** (pas de `push -f`) sans accord explicite.

## 1. Factures → « payé »

Dans `conf/entrypoint-cron.sh`, écrire le bloc avec les ids fournis :

```bash
# Factures de recette passees en "paye" (invoice.status = 2) — jamais en production
if [[ "${ORIGINAL_APP_ENV}" != "prod" ]]; then
    if php bin/console dbal:run-sql --no-interaction \
        "UPDATE invoice SET status = 2, updated_at = NOW() WHERE id IN (<ids>) AND status <> 2"; then
        echo "✅ Factures <ids> : statut 2 (paye) applique"
    else
        echo "⚠️  Echec du passage des factures <ids> en paye"
    fi
fi
```

## 2. Solde d'une entreprise

Même fichier, même emplacement. Le solde d'une société n'est pas un champ : c'est un **journal de
lignes** (`report_om_paiement_balance`), une ligne par méthode de paiement et par instant. Le solde
courant d'un couple (société, méthode) = la ligne de **plus grand `id`**. « Mettre un solde » =
ajouter une ligne avec le montant voulu et la date du jour.

```bash
# Solde de recette : <montant> sur <id company> / <id methode> — jamais en production
if [[ "${ORIGINAL_APP_ENV}" != "prod" ]]; then
    php bin/console dbal:run-sql --no-interaction \
        "INSERT INTO report_om_paiement_balance (balance, company_id, paiement_method_id, date)
         VALUES (<montant>, <id company>, <id methode>, NOW())"
fi
```

- `balance` = le montant, `company_id` = l'entreprise, `paiement_method_id` = la méthode,
  `date = NOW()` = maintenant (c'est ce qui en fait le solde courant).

## 3. Livrer puis vérifier

Commit + push sur la branche fournie, puis Jenkins `jenkinsfile-dev` (`DEPLOY_ACTION=Deploy`,
`BRANCH_ENVIRONMENT=<branche>`). À chaque déploiement, le conteneur CRON rejoue le bloc.

```bash
sudo docker logs orangemoney_cron-mi 2>&1 | tail -20
sudo docker exec orangemoney_cron-mi php bin/console dbal:run-sql \
  "SELECT id, status FROM invoice WHERE id IN (<ids>)"
sudo docker exec orangemoney_cron-mi php bin/console dbal:run-sql \
  "SELECT id, balance, paiement_method_id, date FROM report_om_paiement_balance WHERE company_id = <id company> ORDER BY id DESC LIMIT 5"
```

UI : factures → liste des demandes de paiement (`/fr/backend/invoice/list/`) · solde →
`/fr/dashboard/` (carte de la méthode).

## Pièges

- `dbal:run-sql` n'affiche un résultat que si le SQL commence par `SELECT`.
- La base locale `orangeMoneyTest` n'a pas les données de recette : les ids fournis n'y existent pas.
  Pour tester en local, prendre des ids locaux puis **restaurer la base** après coup.
