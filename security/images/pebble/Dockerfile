# Replace only Canonical Pebble 1.32.2 built with vulnerable Go 1.26.7.
# Rebuild same upstream release using Go 1.26.9; preserve service runtime and volumes.
ARG APP
FROM --platform=$BUILDPLATFORM golang:1.26.9-alpine AS pebble_build
ENV GOTOOLCHAIN=local CGO_ENABLED=0
RUN go install -trimpath github.com/canonical/pebble/cmd/pebble@v1.32.2 \
 && go version -m /go/bin/pebble | grep 'go1.26.9' \
 && /go/bin/pebble version

FROM docker.io/linuxserver/${APP}:latest
COPY --from=pebble_build --chmod=0755 /go/bin/pebble /usr/bin/pebble
