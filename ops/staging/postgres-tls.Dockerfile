# PostgreSQL with TLS, because the runtime cannot connect without it.
#
# `khepri.runtime.config._database_url` builds every URL with
# `query={"sslmode": "require"}` and offers no override, so a plaintext PostgreSQL
# is not merely less secure here -- it is unreachable by the image under test.
#
# The certificate is COPYed rather than bind-mounted. PostgreSQL refuses to start
# when its private key is group- or world-readable, and a Windows bind mount
# presents every file as 0777 regardless of the permissions on the host, so the
# key must enter the image where its mode and owner can be set.
FROM postgres:17.11-alpine

COPY certs/server.crt /var/lib/postgresql/tls/server.crt
COPY certs/server.key /var/lib/postgresql/tls/server.key

RUN chown -R postgres:postgres /var/lib/postgresql/tls \
    && chmod 600 /var/lib/postgresql/tls/server.key \
    && chmod 644 /var/lib/postgresql/tls/server.crt
