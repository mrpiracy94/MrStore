# syntax=docker/dockerfile:1.7
# Exact Qui release with patched Go stdlib and x/net (same fix family as Gitea).
FROM --platform=$BUILDPLATFORM node:24.15-alpine AS frontend
RUN apk add --no-cache git && npm install -g corepack@latest && corepack enable
WORKDIR /src
RUN git clone --depth 1 --branch v1.31.1 https://github.com/autobrr/qui.git . && \
    test "$(git rev-parse HEAD)" = "3cd6f2954549b2adf5f4fdf724788fb06396a7cb"
WORKDIR /src/web
RUN pnpm install --frozen-lockfile && pnpm run build

FROM --platform=$BUILDPLATFORM golang:1.27.2-alpine3.23 AS binary
ARG TARGETOS=linux
ARG TARGETARCH
RUN apk add --no-cache git
WORKDIR /src
RUN git clone --depth 1 --branch v1.31.1 https://github.com/autobrr/qui.git . && \
    test "$(git rev-parse HEAD)" = "3cd6f2954549b2adf5f4fdf724788fb06396a7cb"
RUN go get golang.org/x/net@v0.60.0 && go mod tidy && \
    test "$(go list -m -f '{{.Version}}' golang.org/x/net)" = "v0.60.0"
COPY --from=frontend /src/web/dist /src/web/dist
RUN test "$TARGETOS" = linux && \
    CGO_ENABLED=0 GOOS="$TARGETOS" GOARCH="$TARGETARCH" go build -trimpath \
    -ldflags "-s -w -X github.com/autobrr/qui/internal/buildinfo.Version=v1.31.1 -X github.com/autobrr/qui/internal/buildinfo.Commit=3cd6f2954549b2adf5f4fdf724788fb06396a7cb" \
    -o /qui ./cmd/qui && \
    go version -m /qui | grep -F 'go1.27.2' && \
    go version -m /qui | grep -F 'golang.org/x/net' | grep -F 'v0.60.0'

FROM alpine:3.23
RUN apk add --no-cache ca-certificates curl tzdata bash su-exec
ENV HOME=/config XDG_CONFIG_HOME=/config XDG_DATA_HOME=/config
WORKDIR /config
VOLUME /config
COPY --from=binary --chmod=0755 /qui /usr/local/bin/qui
COPY --from=binary --chmod=0755 /src/distrib/docker/entrypoint.sh /entrypoint.sh
RUN PUID=99 PGID=100 su-exec 99:100 /entrypoint.sh --version
EXPOSE 7476
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:7476/health || exit 1
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
LABEL org.opencontainers.image.source="https://github.com/mrpiracy94/MrStore" \
      org.opencontainers.image.description="Qui v1.31.1 Go stdlib/x-net security rebuild"
