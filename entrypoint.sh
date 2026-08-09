#!/bin/sh
set -e

echo "Aguardando o PostgreSQL..."
python - <<'PY'
import asyncio
import os

import asyncpg


async def wait_for_db() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("DATABASE_URL não configurada")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    connect_args = {}
    ssl = os.environ.get("DATABASE_SSL", "").strip().lower()
    if ssl not in ("", "disable", "false", "0", "off", "none"):
        connect_args["ssl"] = ssl
    for _ in range(30):
        try:
            conn = await asyncpg.connect(url, **connect_args)
            await conn.close()
            return
        except Exception:
            await asyncio.sleep(1)
    raise SystemExit("PostgreSQL não ficou pronto a tempo")


asyncio.run(wait_for_db())
PY

echo "Aplicando migrations..."
alembic upgrade head

echo "Iniciando o bot..."
exec python -m app.main
