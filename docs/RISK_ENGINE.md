# Risk engine

The risk engine sits between every signal and the user. It can veto any signal; nothing
overrides it. Everything that touches money is exact `Decimal` maths. Nothing here places an
order (there is no broker integration yet).

## Limits (environment variables)

Set your own values in the git-ignored `.env` at the repo root. Defaults are conservative.
Values outside the hard ceilings are rejected when the API starts.

| Variable | Default | Hard limit | Meaning |
| --- | --- | --- | --- |
| `RISK_CAPITAL` | 1000 | > 0 | Money at work, in USDT. A placeholder: set your own |
| `RISK_RISK_PER_TRADE_PCT` | 0.5 | 0 to 2 | Loss if the stop is hit, percent of capital |
| `RISK_MAX_CAPITAL_SHARE_PCT` | 20 | 0 to 100 | Largest share of capital in one position |
| `RISK_MAX_DAILY_LOSS_PCT` | 2 | 0 to 10 | No new entries once today's losses reach this |
| `RISK_MAX_OPEN_POSITIONS` | 3 | 1 to 20 | Most positions open at once |
| `RISK_MIN_RISK_REWARD` | 1.5 | at least 1 | Smallest accepted reward per unit of risk |
| `RISK_STOP_ATR_MULTIPLE` | 1.5 | 0.5 to 10 | Stop distance in ATR (average candle range) |
| `RISK_TARGET_ATR_MULTIPLE` | 3 | 0 to 20 | Target distance in ATR |
| `RISK_MAX_STOP_DISTANCE_PCT` | 10 | 0 to 50 | Refuse a stop further than this below the entry |
| `RISK_ADMIN_TOKEN` | unset | | Needed to switch the kill switch OFF through the API |

Also rejected: a target/stop pair whose risk-to-reward is below the minimum (every trade would
be vetoed) and a per-trade risk above the daily loss limit.

## How a BUY is checked

1. **Plan** (`app/risk/plan.py`): stop = entry - stop multiple x ATR, target = entry + target
   multiple x ATR. Vetoed if the stop would be at or below zero, too far away, or the
   risk-to-reward is below the minimum. Stops round away from the entry, targets toward it.
2. **Size** (`app/risk/sizing.py`): quantity = (capital x risk%) / (entry - stop), limited to the
   capital-share cap, rounded down to the instrument's lot size. The real risk and exposure never
   exceed the limits.
3. **Limits:** no new BUY when the open-position limit is reached or today's realised losses
   reached the daily loss limit. (There are no paper trades yet, so these inputs are empty until
   Phase 12; the checks are tested and live.)
4. **Veto:** anything refused becomes **NO TRADE** with every reason. SELL, HOLD and NO TRADE pass
   through unchanged. The stored signal keeps what the rules said (`rules_action`) next to the
   final action, the plan, the size, the vetoes and a snapshot of the limits.

## Nothing skips the veto

- A signal is built only by `to_signal` in `app/signals/runner.py`, which needs a `RiskAssessment`.
  A `RiskAssessment` can only be created by `assess()`.
- `record_signal` refuses a signal without an assessment, and a BUY without its plan and size.
- The database refuses a BUY row without them too (`ck_signals_buy_has_plan`).
- `tests/test_risk_bypass.py` fails if any other module touches the Signal model, calls
  `record_signal`, or writes to the signals table with raw SQL.

## Kill switch

One switch that makes every signal NO TRADE. State is an append-only audit log in the database
(who, when, why), so it survives restarts.

```bash
cd apps/api
uv run python -m app.risk.killswitch status
uv run python -m app.risk.killswitch on  --reason "exchange outage"
uv run python -m app.risk.killswitch off --reason "checked, all clear"
```

API: `GET /risk/status`, `POST /risk/kill-switch {"active": true, "reason": "..."}`. Switching ON
needs nothing. Switching OFF needs `RISK_ADMIN_TOKEN` in the `X-Admin-Token` header, and is refused
when no token is configured (then use the command line). The web proxy does not forward `/risk`.

## Not built yet

Orders and any broker (Phase 12+), real open-position and daily-loss numbers (Phase 12), shorting,
leverage, and per-instrument limits.
