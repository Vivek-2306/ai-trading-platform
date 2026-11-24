"""Tests for the database helpers that don't need a running database."""

from sqlalchemy import Column, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.database import check_database, create_engine
from app.data.base import Base


def test_engine_uses_configured_url() -> None:
    settings = Settings(
        _env_file=None, database_url="postgresql+asyncpg://u:p@db.example:5432/trading"
    )

    engine = create_engine(settings)

    assert isinstance(engine, AsyncEngine)
    assert engine.url.host == "db.example"
    assert engine.url.database == "trading"


async def test_check_database_false_when_unreachable() -> None:
    engine = create_engine(
        Settings(_env_file=None, database_url="postgresql+asyncpg://u:p@127.0.0.1:1/none")
    )
    try:
        assert await check_database(engine, timeout_seconds=1) is False
    finally:
        await engine.dispose()


def test_naming_convention_names_constraints() -> None:
    parent = Table("parent_t", Base.metadata, Column("id", Integer, primary_key=True))
    child = Table(
        "child_t",
        Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey("parent_t.id")),
        Column("code", String(10)),
        UniqueConstraint("code"),
    )
    try:
        names = {constraint.name for constraint in child.constraints}
        assert "pk_child_t" in names
        assert "uq_child_t_code" in names
        assert "fk_child_t_parent_id_parent_t" in names
    finally:
        Base.metadata.remove(child)
        Base.metadata.remove(parent)
