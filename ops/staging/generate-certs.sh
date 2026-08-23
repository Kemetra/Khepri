#!/bin/sh
# Self-signed TLS material for the local staging stack.
#
# `khepri.runtime.config` builds every database URL with `sslmode=require` and
# offers no override, so a non-TLS PostgreSQL is not connectable by the runtime
# image at all. `require` encrypts without verifying the chain, so a self-signed
# pair is sufficient for PostgreSQL. MinIO is verified by botocore, so its cert is
# issued by a local CA that the client trusts through `AWS_CA_BUNDLE`.
#
# Nothing here is a secret and nothing here may be reused: this material exists so
# the staging stack exercises the same TLS paths the runtime will use in a
# provisioned environment.
set -eu
# The directory is gitignored, so on a clean checkout it does not exist and this
# script IS the documented first command -- `cd` into an absent directory would
# fail before anything is generated. `set -e` does not save a `cd` inside a `sh`
# script invoked as `sh script.sh`, which exits 0 regardless, so a caller chaining
# commands would go on to start a stack with no certificates at all.
certs="$(dirname "$0")/certs"
mkdir -p "$certs/minio"
cd "$certs"

if [ -f minio/public.crt ] && [ -f server.crt ] && [ -f ca.crt ]; then
  echo "[OK] certificates already present"
  exit 0
fi

# One local CA, so the MinIO leaf can be verified rather than blindly trusted.
openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
  -keyout ca.key -out ca.crt -subj "/CN=khepri-local-staging-ca" 2>/dev/null

# PostgreSQL: self-signed is enough, because `sslmode=require` does not verify.
openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
  -keyout server.key -out server.crt -subj "/CN=postgres" 2>/dev/null

# MinIO: issued by the CA above, with the service name the containers resolve and
# the host name a developer's browser uses.
openssl req -newkey rsa:2048 -nodes -keyout minio/private.key \
  -out minio.csr -subj "/CN=minio" 2>/dev/null
printf 'subjectAltName=DNS:minio,DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n' > minio.ext
openssl x509 -req -in minio.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out minio/public.crt -days 3650 -sha256 -extfile minio.ext 2>/dev/null
cp ca.crt minio/ca.crt
rm -f minio.csr minio.ext

# PostgreSQL refuses to start if its key is group- or world-readable, and it reads
# the key as uid 999 inside the container.
chmod 600 server.key minio/private.key
chmod 644 server.crt ca.crt minio/public.crt
echo "[OK] certificates generated"
