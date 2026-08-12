#!/bin/sh
set -e

echo "Waiting for MySQL at ${DB_HOST:-mysql}:${DB_PORT:-3306}..."
python3 - <<'PYEOF'
import os
import sys
import time

import pymysql

host = os.getenv("DB_HOST", "mysql")
port = int(os.getenv("DB_PORT", "3306"))
user = os.getenv("DB_USER", "eakms_user")
password = os.getenv("DB_PASSWORD", "")
database = os.getenv("DB_NAME", "eakms_db")

deadline = time.time() + 60
last_error = None
while time.time() < deadline:
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
        conn.close()
        print("MySQL is ready.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last_error = exc
        time.sleep(2)

print(f"MySQL did not become ready in time: {last_error}", file=sys.stderr)
sys.exit(1)
PYEOF

echo "Applying database migrations..."
flask db upgrade

echo "Seeding fixed roles..."
flask seed-roles

echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 3 --timeout 120 "run:app"
