# Risks, compliance and decisions

As of 2026-11-23. The biggest risks are fake accuracy from overfitted backtests and
regulation, not technology.

## Risks

| Risk | Mitigation |
| --- | --- |
| Backtests look great, live results don't (overfitting, look-ahead bias) | Walk-forward only, locked out-of-sample period, costs + slippage modelled, paper trading before real money |
| Stale or wrong market data | Freshness checks per feed; no signal on stale data; cross-check two sources |
| LLM invents facts or numbers | LLM never sets prices or sizes; structured outputs; every claim links to its source |
| A bug places bad orders | Paper mode default, hard risk limits, kill switch, property tests on sizing |
| Costs run away | Budget alerts; LLM only on shortlisted candidates |
| Broker/exchange API changes | One adapter per broker behind a common interface, contract tests |

## Compliance notes (India) — not legal advice

- **Signals for others:** public buy/sell recommendations generally need SEBI Research
  Analyst registration. Personal use does not.
- **Automated orders:** SEBI retail algo rules route API orders through broker approval, a
  registered static IP, and algo registration above order-rate thresholds. Check with the
  broker before enabling automation.
- **Forex:** Indian residents may trade only exchange-traded currency pairs on NSE/BSE.
  Offshore Forex brokers (e.g. OANDA) are not permitted for Indian residents under FEMA.
  For the owner, Forex = currency derivatives via the Indian broker.
- **Crypto:** 30% tax on gains, 1% TDS. Use FIU-IND registered exchanges.
- **Data licences:** personal use is covered by broker/API terms; showing data to others
  needs redistribution licences.

Get a SEBI-focused lawyer's view before any public launch.

## Owner decisions needed

Mirrored in `docs/PROGRESS.md` → Open questions. Record answers there and here.

- [x] Personal tool only (answered 2026-11-24).
- [x] MVP markets: crypto first, Indian markets later (2026-11-24).
- [ ] Indian broker: undecided, not urgent until Indian markets start.
- [x] MVP hosting: single server; Docker + free tiers in development (2026-11-24).
- [x] Budget: near zero in development; cloud plans later (2026-11-24).
- [x] Mobile app: after the web app (2026-11-24).
