"""Nothing may store a signal without the risk veto. These tests fail if a new code path does.

The rule: a `Signal` is built only by `to_signal` in the signal runner (which needs a
RiskAssessment, and a RiskAssessment can only come from `assess`), and stored only by
`record_signal`. The database also refuses a BUY without a plan (tested in the integration
suite).
"""

import ast
from pathlib import Path

import pytest

from app.data.models import Signal
from app.data.repository import record_signal

APP = Path(__file__).resolve().parents[1] / "app"

# Modules that may mention the Signal model at all.
MAY_USE_SIGNAL = {
    "data/models/signals.py",  # the definition
    "data/models/__init__.py",  # the export
    "data/repository.py",  # record_signal (the one writer)
    "signals/runner.py",  # to_signal (the one builder)
    "api/signals.py",  # read-only endpoints
}
MAY_CALL_RECORD_SIGNAL = {"signals/runner.py", "data/repository.py"}


def _python_files() -> list[tuple[str, ast.Module]]:
    return [
        (str(path.relative_to(APP)), ast.parse(path.read_text()))
        for path in sorted(APP.rglob("*.py"))
    ]


def test_only_the_runner_and_repository_touch_the_signal_model() -> None:
    offenders = []
    for name, tree in _python_files():
        used = any(isinstance(node, ast.Name) and node.id == "Signal" for node in ast.walk(tree))
        if used and name not in MAY_USE_SIGNAL:
            offenders.append(name)

    assert offenders == [], f"these modules use Signal without going through the veto: {offenders}"


def test_only_the_runner_calls_record_signal() -> None:
    offenders = []
    for name, tree in _python_files():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if called == "record_signal" and name not in MAY_CALL_RECORD_SIGNAL:
                    offenders.append(name)

    assert offenders == [], f"record_signal called outside the runner: {offenders}"


def test_no_raw_sql_writes_to_the_signals_table() -> None:
    offenders = []
    for name, tree in _python_files():
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = " ".join(node.value.lower().split())
                if "insert into signals" in text or "update signals" in text:
                    offenders.append(name)

    assert offenders == [], f"raw SQL writes to signals found in: {offenders}"


def test_the_runner_builds_every_signal_from_an_assessment() -> None:
    source = (APP / "signals/runner.py").read_text()
    tree = ast.parse(source)
    functions = {
        n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }

    parameters = [a.arg for a in functions["to_signal"].args.args]
    assert "assessment" in parameters
    # and run_signal calls assess() before to_signal()
    run_signal = ast.get_source_segment(source, functions["run_signal"]) or ""
    assert run_signal.index("assess(") < run_signal.index("to_signal(")


async def test_record_signal_refuses_a_signal_without_an_assessment() -> None:
    bare = Signal(
        instrument_id=1,
        timeframe="1h",
        candle_ts=None,
        action="HOLD",
        confidence=0,
        reasons=[],
        inputs={},
        rule_version="rules-v1",
    )

    with pytest.raises(ValueError, match="risk engine's assessment"):
        await record_signal(None, bare)  # type: ignore[arg-type]


async def test_record_signal_refuses_a_buy_without_its_plan() -> None:
    buy = Signal(
        instrument_id=1,
        timeframe="1h",
        candle_ts=None,
        action="BUY",
        confidence=0,
        reasons=[],
        inputs={},
        rule_version="rules-v1",
        risk={"assessed": True},
    )

    with pytest.raises(ValueError, match="trade plan and size"):
        await record_signal(None, buy)  # type: ignore[arg-type]
