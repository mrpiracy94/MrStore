# Karakeep / Meilisearch 1.13.3 → 1.54.3 — migration checklist

**Do not upgrade a live ZimaOS installation without a tested backup.**
This is a proposed security update, not a claim that all existing Karakeep
installations can migrate automatically. CI only checks a *synthetic* database.

## Why

MrStore uses Karakeep with a separate persistent Meilisearch database.
The older image getmeili/meilisearch:v1.13.3 has known HIGH/CRITICAL
vulnerability reports. Meilisearch v1.54.3 includes upstream security
and stability fixes, but the on-disk index format has changed. The stable
migration mechanism is the Meilisearch 1.51+ **--upgrade-db** flag.

Official sources:
- https://www.meilisearch.com/blog/september-2026-updates
- https://www.meilisearch.com/blog/update-meilisearch-digitalocean-aws-gcp
- https://github.com/karakeep-app/karakeep/blob/main/docker/docker-compose.yml

## Before changing anything on an installed server

1. Record the currently installed Karakeep and Meilisearch image tags. Confirm
   adequate free disk space and that the ZimaOS paths below are correct.
2. Verify the Karakeep database and Meilisearch secret. The two
   MEILI_MASTER_KEY values must match and must **not** be left as CHANGE_ME.
3. Stop Karakeep, its Chrome service and Meilisearch. Stop all writers before
   copying database files.
4. Copy **both complete directories** to a different backup location:
   - /DATA/AppData/karakeep/data — Karakeep's authoritative records
   - /DATA/AppData/karakeep/meili — Meilisearch's existing indexes
5. Verify the backups are readable and perform a restore dry run on another
   instance. Keep a copy of the old images or exact tags for rollback.
6. Only then deploy the new Meilisearch image with:
   command: ["meilisearch", "--upgrade-db"]
7. Wait for the migration to complete. Test search, bookmarks, ingestion and
   authentication in Karakeep; inspect both services' logs. Keep the backups
   until several normal runs succeed.

## Recovery

If the upgrade fails, stop all involved containers. **Do not** point the
v1.13.3 binary at a database already migrated by v1.54.3. Restore the original
Karakeep and Meilisearch directories from the *pre-upgrade* backup and revert
both images to their previous recorded tags. Confirm that the original dataset
and indexes are accessible.

The PR's Docker test creates disposable data with the old image and checks
that a saved document remains readable after launching the new image with
--upgrade-db. It does not prove compatibility with a user's private dataset
or with the ZimaOS update UX. Existing systems must be tested individually.

## Verified image and scope

The image reference is pinned to the exact multi-architecture digest that passed 0 HIGH/CRITICAL scans on AMD64 and ARM64:

`getmeili/meilisearch:v1.54.3@sha256:e68913ab7d6f5b159529e472cfd362ce3c741fafd3c127961b2142abbe41b3c9`

This reduces registry tag-drift risk; it does not prove a real ZimaOS upgrade is safe. The scan applies to the **Meilisearch** container only. The other Karakeep/Chrome image vulnerabilities must be tracked separately.

**Approval for existing installations remains blocked** until a real backup and restore test on a representative installation have been confirmed. The migration command upgrades the persistent database format; rollback requires restoring the pre-upgrade files.
