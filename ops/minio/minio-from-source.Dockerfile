# MinIO server and client, built from their pinned release tags (#631).
#
# **Why this is built rather than pulled.** Open-source MinIO is archived. The
# `minio/minio` and `minio/mc` Docker Hub repositories return 404, and dl.min.io
# returns 410 for every community binary. Upstream ships source only, and the release
# tags are still on GitHub. Both compose stacks therefore build the same releases they
# used to pull. Nothing changes except where the bytes come from.
#
# **This carries no security updates.** An archived project publishes no fixes and no
# advisories, so this image is as current as the day the tag was cut, and it must
# never leave a developer's machine. Replacing MinIO with a maintained S3-compatible
# server is the open half of #631. The storage contract in `khepri.rra.storage` names
# no provider, so swapping the server changes only this file and the two compose files.
#
# **The pin is the commit, not the tag.** A tag can be moved and a commit cannot. Each
# build clones its tag and then fails unless HEAD is the full SHA the tag dereferences
# to (`git ls-remote <repo> refs/tags/<tag>^{}`). The annotated tag object has a
# different SHA, and HEAD never equals it.
#
# **Built the way upstream's Makefile builds it**: `CGO_ENABLED=0`, `-tags kqueue
# -trimpath`, and the ldflags from `buildscripts/gen-ldflags.go`, given the release
# time. `--version` therefore reports the release tag and commit, not `DEVELOPMENT`.
# `GOTOOLCHAIN=local` keeps the build on the pinned Go instead of downloading another.
#
# **It runs as root, as the upstream image did.** Staging mounts MinIO's TLS pair at
# `/root/.minio/certs`, where the server looks through `$HOME`, and `minio-init`
# installs its CA under `/root/.mc/certs/CAs`.
#
# The `*_TAG` names are deliberate. `gen-ldflags.go` reads `MINIO_RELEASE` and
# `MC_RELEASE` as the release prefix, and a build ARG with either name would leak
# into that environment and corrupt the reported version.

ARG MINIO_TAG=RELEASE.2025-09-07T16-13-09Z
ARG MINIO_COMMIT=07c3a429bfed433e49018cb0f78a52145d4bedeb
ARG MC_TAG=RELEASE.2025-08-13T08-35-41Z
ARG MC_COMMIT=7394ce0dd2a80935aded936b09fa12cbb3cb8096

FROM golang:1.24.13-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS server-build
ARG MINIO_TAG
ARG MINIO_COMMIT
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
# `RELEASE.2025-09-07T16-13-09Z` names the time `2025-09-07T16:13:09Z`, which is the
# form upstream passes to `gen-ldflags.go`.
RUN git clone --depth 1 --branch "${MINIO_TAG}" https://github.com/minio/minio /src \
    && cd /src \
    && test "$(git rev-parse HEAD)" = "${MINIO_COMMIT}" \
    && released="$(echo "${MINIO_TAG#RELEASE.}" | sed -E 's/T([0-9]+)-([0-9]+)-([0-9]+)Z$/T\1:\2:\3Z/')" \
    && go build -tags kqueue -trimpath \
        -ldflags "$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${released}")" \
        -o /out/minio .

FROM golang:1.24.13-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS client-build
ARG MC_TAG
ARG MC_COMMIT
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
RUN git clone --depth 1 --branch "${MC_TAG}" https://github.com/minio/mc /src \
    && cd /src \
    && test "$(git rev-parse HEAD)" = "${MC_COMMIT}" \
    && released="$(echo "${MC_TAG#RELEASE.}" | sed -E 's/T([0-9]+)-([0-9]+)-([0-9]+)Z$/T\1:\2:\3Z/')" \
    && go build -tags kqueue -trimpath \
        -ldflags "$(MC_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${released}")" \
        -o /out/mc .

# The client: staging's `minio-init` overrides the entrypoint with `/bin/sh -c`.
FROM debian:12.15-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251 AS client
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=client-build /out/mc /usr/bin/mc
ENTRYPOINT ["mc"]

# The server, last so that a build with no target produces it. `curl` is the healthcheck.
FROM debian:12.15-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251 AS server
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=server-build /out/minio /usr/bin/minio
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["minio"]
CMD ["server", "/data"]
