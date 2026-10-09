# Target only the OS dependency layer of the official Gitea rootful image.
# Rootless images are NOT compatible with existing /data/SSH layout.
FROM docker.io/gitea/gitea:latest
USER root
RUN apk upgrade --no-cache
# No ENTRYPOINT, CMD, VOLUME, USER_UID, USER_GID or port override.
