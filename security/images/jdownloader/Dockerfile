# Keep the complete official JDownloader 2 runtime, init, UI, ports and volumes.
# Only apply vendor-provided Alpine security updates.
# CI resolves v26.09.1 to one immutable multiarch upstream digest before building.
ARG UPSTREAM_IMAGE=docker.io/jlesage/jdownloader-2:v26.09.1
FROM ${UPSTREAM_IMAGE}

RUN apk upgrade --no-cache
