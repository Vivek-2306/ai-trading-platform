# ADR 0003: Feature architecture: ccxt adapters, gold source, risk veto, backtest first

- Status: Accepted
- Date: 2026-11-24

## Context

The setup is done (v0.1.0). Feature work starts with crypto and gold for a personal tool,
swing trading first, scalping researched soon after. Costs must stay near zero in
development. Accuracy must be measured, not assumed.

## Decision

1. **Market data via adapters.** Every exchange or data provider sits behind one adapter
   interface with contract tests on recorded fixtures. Crypto uses `ccxt` against Binance
   public data (no API key). Adding an exchange means adding an adapter, not changing callers.
2. **Gold (XAU/USD).** Binance spot has no true XAU/USD. Use a free forex data API
   (candidate: Twelve Data) with `PAXG/USDT` on Binance as a free cross-check. Ticket
   AITP-43 compares the sources and records the final choice and free-tier limits below.
   If free limits are too tight, ship PAXG only until a paid plan is justified.
3. **Spot, long-only, no leverage** for v1.
4. **Timeframes are parameters from the start.** The candle schema and signal and backtest
   code take a timeframe, so scalping (1m/5m) reuses the swing code path.
5. **The risk engine is a mandatory veto.** Every signal passes through it; a test fails if
   any code path bypasses it. The LLM never sizes or places orders.
6. **Backtest before any strategy is trusted.** Walk-forward, costs and slippage modelled,
   a locked out-of-sample period. This includes scalping: a strategy moves to paper trading
   only if it beats costs out-of-sample.
7. **Order of work:** data → live stream → rule signals → risk → backtest → scalping
   research → ML → news/AI → paper trading.

## Consequences

- Easier: adding exchanges, timeframes and strategies; honest accuracy numbers.
- Harder: gold needs a second provider and market-hours-aware gap checks (crypto is 24/7).
- Watch: scalping may show no edge after fees; that is a valid result, not a failure.
- **Gold source decision (AITP-43, 2026-11-24):**
  - Default: `PAXG/USDT` on Binance through the existing `BinanceAdapter`. It works today with no key
    (checked live), so gold data flows from day one, tracking spot gold closely but not exactly.
  - Optional: true `XAU/USD` from Twelve Data through `TwelveDataAdapter`, enabled by setting
    `TWELVE_DATA_API_KEY`. Free plan as checked 2026-11-24: 8 credits per minute, 800 per day, one
    `time_series` call costs 1 credit per symbol. That is plenty for hourly and daily candles of one
    symbol. Forex pairs have no volume (stored as 0). I could not confirm from public docs that XAU/USD
    is included in the free plan, and the adapter's tests use a fixture written from the documented
    response format, not a live recording. First step once a key exists: one live call to verify.
  - Gold trades Monday to Friday only while PAXG trades 24/7, so gap checks must know the venue's hours.
