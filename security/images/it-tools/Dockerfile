# Preserve the upstream static web app byte-for-byte, but retire its old
# nginx:stable-alpine base (Alpine 3.20, 2024) with unpatched system packages.
# The manifest SHA is the upstream multi-architecture image index.
FROM corentinth/it-tools@sha256:8b8128748339583ca951af03dfe02a9a4d7363f61a216226fc28030731a5a61f AS upstream

FROM nginx:stable-alpine
RUN apk upgrade --no-cache
COPY --from=upstream /usr/share/nginx/html/ /usr/share/nginx/html/
COPY --from=upstream /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
