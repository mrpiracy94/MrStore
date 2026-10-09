# Security-patched derivative of the maintained netboot.xyz container.
# Do not publish or use this image until Trivy has verified both architectures.
FROM ghcr.io/netbootxyz/netbootxyz:latest

USER root
RUN set -eux; \
    apk upgrade --no-cache; \
    apk add --no-cache --virtual .mrstore-security-npm npm; \
    cd /app; \
    npm update --omit=dev --no-audit --no-fund; \
    npm install --omit=dev --no-audit --no-fund --save-exact systeminformation@5.31.7; \
    npm cache clean --force; \
    apk del .mrstore-security-npm; \
    rm -rf /root/.npm /tmp/.npm
