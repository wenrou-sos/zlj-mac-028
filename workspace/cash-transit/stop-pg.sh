#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export LD_LIBRARY_PATH="$ROOT/pgsql/local/usr/lib/aarch64-linux-gnu:$ROOT/pgsql/local/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
"$ROOT/pgsql/local/usr/lib/postgresql/15/bin/pg_ctl" -D "$ROOT/pgdata" stop
echo "PostgreSQL 已停止"
