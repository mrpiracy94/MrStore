# Pebble promotion — backup, validation and rollback

This procedure applies to proposed image promotions for ffmpeg, jellyfin and plex. It does not certify runtime compatibility or CVE remediation.

## Before proposing an image update

1. Export a backup of the currently approved `Apps/<app>/docker-compose.yml` files and `data/image-digests.json`, including file checksums and the Git commit SHA. Store it securely outside the deployment host.
2. Back up application configuration and persistent data using the operator's established, application-consistent backup process. Verify that the backup can be restored in an isolated environment. Do not change or delete existing volumes.
3. Capture old and candidate **full** immutable image digests (`sha256:<64 hex>`) and upstream provenance. Validate image manifests and the declared architectures.
4. Scan both old and candidate with Trivy for every declared architecture, retaining full JSON artifacts. Treat HTTP 429, missing results, timeouts, 404 and unsupported platforms as **inconclusive**, never zero vulnerabilities.
5. Require a decrease in observed CRITICAL/HIGH findings on at least one architecture and **no increase in either severity on any declared architecture**. Record CVEs without vendor patches separately.
6. Run catalog validation, unit and regression tests, Compose config checks and isolated runtime smoke tests before requesting review. Explicitly record any runtime compatibility that cannot be certified.
7. Submit the image reference and aligned digest baseline together in a dedicated pull request. Never push a promotion directly to `main` or merge without required checks and review.

## Rollback

1. Stop further rollout if checks fail or if application behavior regresses.
2. Restore the prior approved Compose image reference and its exact baseline entry from the saved Git commit, through a reviewed revert PR. Preserve ports, environment, credentials, bind mounts and named volumes.
3. Recreate only the affected container after operator approval, using the previously pinned image digest. Do not prune volumes or delete application data.
4. If the application altered persistent data or performed irreversible migrations, follow its upstream rollback guidance and restore the verified application-consistent backup. Do not assume that reverting the image also reverts data migrations.
5. Re-run health checks and record the old/new digests, architectures, scanner results, incident link and rollback verification.

## Workflow guardrail

The Pebble build workflow may publish test artifacts after security and smoke checks, but **must not** commit or push catalog image updates to `main`. A separate PR and required checks are mandatory for deployment changes.
