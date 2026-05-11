#!/usr/bin/env sh
set -e
if [ "${NO_LOGS:-}" != "1" ]; then
  mkdir -p /app/logs
  chown -R app:app /app/logs
fi
exec gosu app "$@"
