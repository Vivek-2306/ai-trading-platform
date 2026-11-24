"""Smoke tests: every dependency group imports, and the native ones really compute.

Locally a group that is not installed is skipped (`uv sync --all-groups` installs everything).
In CI, REQUIRE_ALL_PACKAGES=1 turns a missing or broken package into a failure.
"""

import importlib
import os
import tomllib
from pathlib import Path
from typing import Any

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
        "socks",
    ],
}
REQUIRED = os.environ.get("REQUIRE_ALL_PACKAGES") == "1"

# distribution name in pyproject -> import name, where they differ
IMPORT_NAMES = {
    "ta-lib": "talib",
    "scikit-learn": "sklearn",
    "mlflow-skinny": "mlflow",
    "alpaca-py": "alpaca",
    "polygon-api-client": "polygon",
    "finnhub-python": "finnhub",
    "python-telegram-bot": "telegram",
    "exchange-calendars": "exchange_calendars",
    "pysocks": "socks",
}


def _import(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        # error.name is the top-level module that is missing (sklearn for sklearn.linear_model).
        missing_it = error.name == name or name.startswith(f"{error.name}.")
        if missing_it and not REQUIRED:
            pytest.skip(f"{name} is not installed (uv sync --all-groups)")
        raise


@pytest.mark.parametrize("name", [name for names in GROUPS.values() for name in names])
def test_package_imports(name: str) -> None:
    _import(name)


def test_talib_computes_a_moving_average() -> None:
    numpy = _import("numpy")
    talib = _import("talib")

    result = talib.SMA(numpy.arange(10.0), timeperiod=3)

    assert result[-1] == 8.0


def test_polars_and_pandas_agree_on_a_sum() -> None:
    polars = _import("polars")
    pandas = _import("pandas")

    values = [1.0, 2.0, 3.5]

    assert polars.Series(values).sum() == pandas.Series(values).sum()


def test_lightgbm_trains_a_tiny_model() -> None:
    numpy = _import("numpy")
    lightgbm = _import("lightgbm")
    features = numpy.arange(40.0).reshape(20, 2)
    labels = (features[:, 0] > 20).astype(int)

    model = lightgbm.LGBMClassifier(n_estimators=5, min_child_samples=1, verbose=-1)
    model.fit(features, labels)

    assert model.predict(features[:1]).shape == (1,)


# exchange-calendars 4.x uses a pandas API that pandas 3.1 deprecates (a library issue).
@pytest.mark.filterwarnings("ignore:Series.values returning an ndarray")
def test_exchange_calendar_knows_indian_sessions() -> None:
    calendars = _import("exchange_calendars")

    # The library has BSE (XBOM) but no NSE calendar; NSE holidays need their own data later.
    bse = calendars.get_calendar("XBOM")

    assert bse.is_session("2026-01-02")
    assert not bse.is_session("2026-01-03")  # Saturday


def test_vectorbt_runs_a_backtest() -> None:
    pandas = _import("pandas")
    vbt = _import("vectorbt")
    prices = pandas.Series([10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 13.0, 15.0, 16.0, 15.0])
    entries = prices.diff() > 0

    portfolio = vbt.Portfolio.from_signals(prices, entries, ~entries)

    assert portfolio.total_return() == portfolio.total_return()  # a real number, not NaN


def test_sklearn_and_statsmodels_fit() -> None:
    numpy = _import("numpy")
    sklearn_linear = _import("sklearn.linear_model")
    sm = _import("statsmodels.api")
    x = numpy.arange(20.0).reshape(-1, 1)
    y = 3 * x[:, 0] + 1

    slope = sklearn_linear.LinearRegression().fit(x, y).coef_[0]
    ols = sm.OLS(y, sm.add_constant(x)).fit()

    assert abs(slope - 3) < 1e-9
    assert abs(ols.params[1] - 3) < 1e-9


def test_every_declared_dependency_has_a_smoke_test() -> None:
    """A package added to a dependency group must also be added to GROUPS above."""
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    tested = {name for names in GROUPS.values() for name in names}
    missing = []
    for group, requirements in pyproject["dependency-groups"].items():
        if group not in GROUPS:
            continue
        for requirement in requirements:
            dist = requirement.split(">")[0].split("=")[0].split("[")[0].strip().lower()
            if IMPORT_NAMES.get(dist, dist.replace("-", "_")) not in tested:
                missing.append(f"{group}: {dist}")
    assert not missing, f"add to GROUPS: {missing}"
