"""Migration checks that don't need a database (offline SQL generation)."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI))
    # Offline mode only renders SQL; this URL is never connected to.
    config.set_main_option("sqlalchemy.url", "postgresql+asyncpg://u:p@localhost/offline")
    return config


def test_migrations_have_a_single_head(alembic_config: Config) -> None:
    heads = ScriptDirectory.from_config(alembic_config).get_heads()

    assert len(heads) == 1


def test_baseline_enables_extensions(
    alembic_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    command.upgrade(alembic_config, "0001", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE EXTENSION IF NOT EXISTS timescaledb" in sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql


def test_baseline_downgrade_drops_extensions(
    alembic_config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    command.downgrade(alembic_config, "0001:base", sql=True)

    sql = capsys.readouterr().out
    assert "DROP EXTENSION IF EXISTS vector" in sql
    assert "DROP EXTENSION IF EXISTS timescaledb" in sql
