# syntax=docker/dockerfile:1.7
# Pinned upstream source and unchanged Gitea rootful container contract.
# Remediation: Go stdlib >=1.27.2 and golang.org/x/net >=0.60.0.
FROM --platform=$BUILDPLATFORM golang:1.27.2-alpine3.24 AS frontend
RUN apk add --no-cache build-base git make nodejs pnpm
WORKDIR /src
RUN git clone --depth 1 --branch v28.1.0 https://github.com/go-gitea/gitea.git . && \
    test "$(git rev-parse HEAD)" = "4ebd5e319b6a9e629bfd7a04292a6fe85b08dee9"
RUN make frontend

FROM --platform=$BUILDPLATFORM golang:1.27.2-alpine3.24 AS binary
ARG TARGETOS=linux
ARG TARGETARCH
ENV CGO_ENABLED=1
ENV TAGS="bindata timetzdata"
RUN apk add --no-cache build-base git make
WORKDIR /src
RUN git clone --depth 1 --branch v28.1.0 https://github.com/go-gitea/gitea.git . && \
    test "$(git rev-parse HEAD)" = "4ebd5e319b6a9e629bfd7a04292a6fe85b08dee9"
RUN go get golang.org/x/net@v0.60.0 && go mod tidy && \
    test "$(go list -m -f '{{.Version}}' golang.org/x/net)" = "v0.60.0"
COPY --from=frontend /src/public/assets /src/public/assets
# CGO (SQLite) must be compiled natively; the CI uses native AMD64 and ARM64 runners.
RUN test "$TARGETOS" = linux && \
    test "$(go env GOARCH)" = "$TARGETARCH" && \
    make backend && \
    go version -m /src/gitea | grep -F 'go1.27.2' && \
    go version -m /src/gitea | grep -F 'golang.org/x/net' | grep -F 'v0.60.0'

FROM docker.io/gitea/gitea:28.1.0
# Preserve /usr/bin/entrypoint, s6, SSH, /data, UID/GID and ports 3000/22.
RUN apk upgrade --no-cache
COPY --from=binary --chmod=0755 /src/gitea /app/gitea/gitea
RUN /app/gitea/gitea --version | grep -F '28.1.0'
LABEL org.opencontainers.image.source="https://github.com/mrpiracy94/MrStore" \
      org.opencontainers.image.description="Gitea 28.1.0 Go stdlib/x-net security rebuild; rootful contract preserved"
