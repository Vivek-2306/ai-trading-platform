"""Smoke tests: every dependency group imports, and the native ones really compute.

Locally a group that is not installed is skipped (`uv sync --all-groups` installs everything).
In CI, REQUIRE_ALL_PACKAGES=1 turns a missing or broken package into a failure.
"""

import importlib
import os

import pytest

# group -> import names. Keep in step with [dependency-groups] in pyproject.toml.
GROUPS: dict[str, list[str]] = {
    "analysis": [
        "pandas",
        "numpy",
        "polars",
        "scipy",
        "statsmodels",
        "talib",
        "vectorbt",
        "quantstats",
        "exchange_calendars",
    ],
    "ml": ["sklearn", "lightgbm", "optuna", "mlflow", "shap"],
    "ai": ["anthropic", "voyageai", "pgvector"],
    "markets": [
        "kiteconnect",
        "ccxt",
        "alpaca",
        "polygon",
        "finnhub",
        "fredapi",
        "feedparser",
        "trafilatura",
        "telegram",
        "websockets",
        "tenacity",
    ],
}
REQUIRED = os.environ.get("REQUIRE_ALL_PACKAGES") == "1"


def _import(name: str) -> object:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name == name and not REQUIRED:
            pytest.skip(f"{name} is not installed (uv sync --all-groups)")
        raise


@pytest.mark.parametrize("name", [name for names in GROUPS.values() for name in names])
def test_package_imports(name: str) -> None:
    _import(name)


def test_talib_computes_a_moving_average() -> None:
    numpy = pytest.importorskip("numpy")
    talib = _import("talib")

    result = talib.SMA(numpy.arange(10.0), timeperiod=3)  # type: ignore[attr-defined]

    assert result[-1] == 8.0


def test_polars_and_pandas_agree_on_a_sum() -> None:
    polars = _import("polars")
    pandas = _import("pandas")

    values = [1.0, 2.0, 3.5]

    assert polars.Series(values).sum() == pandas.Series(values).sum()  # type: ignore[attr-defined]


def test_lightgbm_trains_a_tiny_model() -> None:
    numpy = pytest.importorskip("numpy")
    lightgbm = _import("lightgbm")
    features = numpy.arange(40.0).reshape(20, 2)
    labels = (features[:, 0] > 20).astype(int)

    model = lightgbm.LGBMClassifier(n_estimators=5, min_child_samples=1, verbose=-1)  # type: ignore[attr-defined]
    model.fit(features, labels)

    assert model.predict(features[:1]).shape == (1,)


def test_exchange_calendar_knows_indian_sessions() -> None:
    calendars = _import("exchange_calendars")

    # The library has BSE (XBOM) but no NSE calendar; NSE holidays need their own data later.
    bse = calendars.get_calendar("XBOM")  # type: ignore[attr-defined]

    assert bse.is_session("2026-01-02")
    assert not bse.is_session("2026-01-03")  # Saturday
