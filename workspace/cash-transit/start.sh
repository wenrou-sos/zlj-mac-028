#!/usr/bin/env bash
# 银卫押运管理系统 —— 一键启动（免 root，内置本地 PostgreSQL）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PGDIR="$ROOT/pgsql/local/usr"
PGBIN="$PGDIR/lib/postgresql/15/bin"
PGDATA="$ROOT/pgdata"
PGPORT=55432
SOCKDIR=/tmp/pgsock
VENV="$ROOT/venv"

# ---------- 1. Python 虚拟环境 ----------
if [ ! -x "$VENV/bin/python" ]; then
  echo "[1/6] 创建 Python 虚拟环境..."
  python3 -m venv --without-pip "$VENV"
  if [ ! -f "$VENV/bin/pip" ]; then
    curl -sS https://bootstrap.pypa.io/get-pip.py | "$VENV/bin/python"
  fi
  "$VENV/bin/pip" install -r "$ROOT/backend/requirements.txt"
fi

# ---------- 2. 本地 PostgreSQL ----------
if [ ! -x "$PGBIN/postgres" ]; then
  echo "[2/6] 下载并解包本地 PostgreSQL 15..."
  mkdir -p "$PGDIR" "$ROOT/pgsql/debs"
  cd "$ROOT/pgsql/debs"
  BASE=http://deb.debian.org/debian/pool/main/p/postgresql-15
  ARCH=$(dpkg --print-architecture 2>/dev/null || uname -m)
  case "$ARCH" in
    arm64|aarch64) ARCH=arm64 ;;
    amd64|x86_64)  ARCH=amd64 ;;
  esac
  for deb in libpq5 postgresql-client-15 postgresql-15; do
    VER=$(curl -s "$BASE/" | grep -oE "${deb}_[0-9][^\"]*_${ARCH}.deb" | sort -V | tail -1)
    [ -f "$VER" ] || curl -fsSLO "$BASE/$VER"
  done
  for deb in *.deb; do dpkg-deb -x "$deb" "$PGDIR/../"; done
  cd "$ROOT"
fi

export LD_LIBRARY_PATH="$PGDIR/lib/aarch64-linux-gnu:$PGDIR/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
mkdir -p "$SOCKDIR"

if [ ! -d "$PGDATA/base" ]; then
  echo "[3/6] 初始化数据库集群..."
  "$PGBIN/initdb" -D "$PGDATA" -U cash --auth-local=trust --auth-host=trust \
    --locale=C.UTF-8 --encoding=UTF8 >/dev/null
  {
    echo "listen_addresses = '127.0.0.1'"
    echo "port = $PGPORT"
    echo "unix_socket_directories = '$SOCKDIR'"
  } >> "$PGDATA/postgresql.conf"
fi

if ! "$PGBIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
  echo "[4/6] 启动 PostgreSQL..."
  "$PGBIN/pg_ctl" -D "$PGDATA" -l "$ROOT/pgsql/pg.log" -w start
  "$PGBIN/psql" -h "$SOCKDIR" -p "$PGPORT" -U cash -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='cash_transit'" | grep -q 1 || \
    "$PGBIN/psql" -h "$SOCKDIR" -p "$PGPORT" -U cash -d postgres -c \
      "CREATE DATABASE cash_transit;"
fi

# ---------- 3. Django ----------
echo "[5/6] 数据库迁移与样例数据..."
cd "$ROOT/backend"
export DB_HOST=127.0.0.1 DB_PORT=$PGPORT DB_NAME=cash_transit DB_USER=cash DB_PASSWORD=cash123
"$VENV/bin/python" manage.py migrate --noinput
DATA_FLAG=$(PGPASSWORD=cash123 "$PGBIN/psql" -h 127.0.0.1 -p "$PGPORT" -U cash -d cash_transit -tAc \
  "SELECT count(*) FROM core_branch;" 2>/dev/null || echo 0)
if [ "${DATA_FLAG:-0}" = "0" ]; then
  "$VENV/bin/python" manage.py init_demo
fi

# ---------- 4. 前端依赖 ----------
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "[6/6] 安装前端依赖..."
  (cd "$ROOT/frontend" && npm install --no-audit --no-fund)
fi

echo ""
echo "================================================================"
echo " 银卫押运管理系统已启动"
echo "   后端 API  : http://127.0.0.1:8000   (管理后台 /admin/)"
echo "   前端页面  : http://127.0.0.1:5173"
echo "   演示账号  : 1001(调度员) / 4001(金库) / 2001(车长) / admin"
echo "   统一密码  : cash123456"
echo "================================================================"

"$VENV/bin/python" manage.py runserver 127.0.0.1:8000 &
DJANGO_PID=$!
(cd "$ROOT/frontend" && npm run dev) &
VITE_PID=$!
trap 'echo; echo "正在停止..."; kill $DJANGO_PID $VITE_PID 2>/dev/null || true' INT TERM
wait
