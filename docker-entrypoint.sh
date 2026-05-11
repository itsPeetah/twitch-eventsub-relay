#!/usr/bin/env sh
set -e
mkdir -p /app/logs
chown -R app:app /app/logs
exec gosu app "$@"
