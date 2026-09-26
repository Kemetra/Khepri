# PostgreSQL with TLS, because the runtime cannot connect without it.
#
# `khepri.runtime.config._database_url` connects to this non-loopback host with
# `sslmode=verify-full`, so a plaintext PostgreSQL is not merely less secure here --
# it is unreachable by the image under test. The leaf is issued by the local CA for
# `DNS:postgres` (`generate-certs.sh`).
#
# The certificate is COPYed rather than bind-mounted. PostgreSQL refuses to start
# when its private key is group- or world-readable, and a Windows bind mount
# presents every file as 0777 regardless of the permissions on the host, so the
# key must enter the image where its mode and owner can be set.
FROM postgres:17.11-alpine

COPY certs/postgres/server.crt /var/lib/postgresql/tls/server.crt
COPY certs/postgres/server.key /var/lib/postgresql/tls/server.key

RUN chown -R postgres:postgres /var/lib/postgresql/tls \
    && chmod 600 /var/lib/postgresql/tls/server.key \
    && chmod 644 /var/lib/postgresql/tls/server.crt
