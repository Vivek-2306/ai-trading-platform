# Cost estimation

As of 2026-11-23. USD per month at ₹88 = $1. Claude prices are Anthropic's published rates;
all other prices are approximate list prices **not verified live** — confirm before subscribing.

**Summary:** MVP ≈ $245/mo (≈ ₹21,500) · Beta ≈ $1,155/mo (≈ ₹1 lakh) · Production ≈ $5,500+/mo
(≈ ₹4.8 lakh+). In production, market-data redistribution licences are the largest, least
certain cost.

| Cost area | MVP: owner only, India + crypto, paper trading | Beta: all markets, few users, small live | Production: public app |
| --- | --- | --- | --- |
| Cloud hosting and databases | $70 | $300 | $1,300 |
| Market data | $35 | $200 | $2,500+ |
| News and macro data | $0 | $50 | $300 |
| AI models (Claude) | $120 | $500 | $1,000 |
| Embeddings (Voyage AI) | $5 | $15 | $50 |
| Monitoring and errors | $0 | $60 | $200 |
| Apps, domain, email, other | $15 | $30 | $150 |
| **Total** | **≈ $245** | **≈ $1,155** | **≈ $5,500+** |

## Cloud hosting

- **MVP:** one 4 vCPU / 8 GB server in Mumbai/Bangalore (DigitalOcean, Hetzner or AWS
  Lightsail, ≈ $48), backups and storage (≈ $15), Vercel Hobby (free).
- **Beta:** second server for workers, managed Postgres + TimescaleDB with daily backups,
  managed Redis, Vercel Pro ($20).
- **Production:** AWS Mumbai: ECS Fargate, Timescale Cloud (AWS RDS lacks TimescaleDB),
  ElastiCache, load balancer, S3, CloudWatch.

## Market data

| Source | Market | Approx. price |
| --- | --- | --- |
| Zerodha Kite Connect | India stocks, F&O, currency derivatives | ₹500 (≈ $6) |
| Financial Modeling Prep | Fundamentals, earnings | $29–69 |
| Polygon.io | US stocks | $29 (Starter) – $199 (Advanced) |
| Alpaca | US stocks (IEX), paper trading | Free |
| Exchanges via ccxt | Crypto | Free |
| OANDA | Forex (non-Indian users) | Free with account |
| TrueData / Global Datafeeds | NSE tick data, beta onward | ≈ $25–90 |

Showing exchange data to other users needs redistribution licences (NSE; Polygon business
plans) — production line needs real quotes.

## News and macro

Finnhub free tier + RSS + FRED for MVP; paid Finnhub or Marketaux at beta. Avoid NewsAPI.org
business (≈ $449); its free tier is non-commercial only.

## AI models (Claude API)

| Model | Job | Input / output per 1M tokens |
| --- | --- | --- |
| Claude Haiku 5.5 (`claude-haiku-5-5`) | Tag/summarise every news item | $0.10 / $0.50 |
| Claude Opus 5.5 (`claude-opus-5-5`) | Final reasoning on shortlisted signals | $4 / $20 (cached input $0.20) |

The LLM runs only on candidates the rules + ML layers flagged, so cost scales with markets
covered, not users (signals are shared).

- MVP: 3,000 news/day on Haiku (≈ $23) + 30 candidates/day on Opus at ~15k in / 2k out (≈ $90).
- Beta: 10,000 news (≈ $75) + 150 candidates (≈ $450).
- Production: 20,000 news (≈ $150) + 300 candidates (≈ $900).

Prompt caching and the Batch API (50% off, for overnight research) can cut this by a third or more.

## One-time and yearly

- Apple Developer $99/yr; Google Play $25 once; domain ≈ $12/yr.
- Legal: SEBI research-analyst registration and legal advice before public signals (quote needed).

## Keeping costs down

- One server until CPU/memory is actually the limit.
- Free broker/exchange APIs before paid vendors.
- LLM only on shortlisted candidates, with caching and batching.
- Add markets one at a time.
- Budget alerts on cloud and Anthropic accounts from day one.
