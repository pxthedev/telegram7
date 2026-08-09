from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config.settings import settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class LazyAsyncSessionFactory:
    """Cria o engine e o sessionmaker somente no primeiro uso."""

    def __init__(self) -> None:
        self._engine = None
        self._factory: async_sessionmaker[AsyncSession] | None = None

    def _ensure(self) -> async_sessionmaker[AsyncSession]:
        if self._factory is None:
            self._engine = create_async_engine(
                settings.database_url,
                pool_pre_ping=True,
                connect_args=settings.database_connect_args,
            )
            self._factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._factory

    def __call__(self, **local_kw: object) -> AsyncSession:
        return self._ensure()(**local_kw)


async_session_factory = LazyAsyncSessionFactory()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
