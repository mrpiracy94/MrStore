# Preserve upstream rootful Gitea entrypoint, port 22/3000 and /data layout.
# Never publish without multiarch zero-HIGH/CRITICAL Trivy scans.
FROM docker.io/gitea/gitea:latest
USER root
RUN apk upgrade --no-cache
