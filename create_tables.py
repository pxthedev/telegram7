#!/usr/bin/env python
"""Cria as tabelas necessárias do banco de dados.

Uso:
    python create_tables.py                 # cria as tabelas faltantes no banco (.env)
    python create_tables.py --sql           # gera schema.sql com o DDL para o SQL Editor do Supabase
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateIndex, CreateTable

import app.database.models  # noqa: F401  # registra os modelos no metadata
from app.config.settings import settings
from app.database.database import Base


def generate_schema_sql() -> str:
    dialect = postgresql.dialect()
    statements: list[str] = []
    for table in Base.metadata.sorted_tables:
        statements.append(
            str(CreateTable(table, if_not_exists=True).compile(dialect=dialect))
        )
        for index in table.indexes:
            statements.append(
                str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect))
            )
    body = ";\n\n".join(statements).strip()
    return (
        "-- Esquema gerado a partir dos modelos (python create_tables.py --sql)\n"
        "-- Idempotente: pode ser executado mais de uma vez (IF NOT EXISTS).\n\n"
        + body
        + ";\n"
    )


async def create_tables() -> None:
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args=settings.database_connect_args,
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def list_tables() -> None:
    engine = create_async_engine(
        settings.database_url,
        connect_args=settings.database_connect_args,
    )
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' ORDER BY tablename"
                )
            )
            tables = [row[0] for row in result]
    finally:
        await engine.dispose()

    print("Tabelas presentes no banco:")
    for name in tables:
        print(f"  - {name}")


def main() -> None:
    if "--sql" in sys.argv:
        sql = generate_schema_sql()
        with open("schema.sql", "w", encoding="utf-8") as fh:
            fh.write(sql)
        print("schema.sql gerado — cole o conteúdo no SQL Editor do Supabase.")
        return

    asyncio.run(create_tables())
    print("Tabelas verificadas/criadas com sucesso.")
    asyncio.run(list_tables())


if __name__ == "__main__":
    main()
