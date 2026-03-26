---
name: rekko
description: Prediction market intelligence from Rekko AI — deep causal research, arbitrage detection, screening, real-time signals, and strategy for autonomous trading agents.
---

# Rekko — Prediction Market Intelligence

## What is Rekko?

Rekko AI provides deep causal research for prediction markets on Kalshi, Polymarket, and Robinhood. It is the intelligence layer ("the brain") that sits alongside execution skills:

- **PolyClaw** — executes trades on Polymarket
- **Kalshi Trader** — executes trades on Kalshi
- **Rekko** (this skill) — provides the WHY behind market movements

Rekko runs multi-stage research pipelines that analyze prediction market bets, produce probability estimates with confidence levels, and return actionable strategy signals with causal decomposition. You consume finished insights; Rekko handles all research internally.

Payment is per-request via x402 (USDC on Base L2) or through an API key.

## Setup

### HTTP Client (recommended)

```
Base URL: https://api.rekko.ai/v1
```

Authentication options:
1. **x402** — automatic USDC micropayment per request (recommended for autonomous agents)
2. **API key** — `Authorization: Bearer <key>` header

#### x402 Autopay Setup

1. Fund an EVM wallet with USDC on **Base mainnet** (chain ID 8453)
2. Install dependencies: `pip install httpx x402[fastapi] eth-account`
3. Create a client:

```python
from eth_account import Account
from rekko_tools import RekkoClient

signer = Account.from_key("0x<your-private-key>")
async with RekkoClient(signer=signer) as client:
    markets = await client.list_markets()
```

Or set `X402_PRIVATE_KEY` in your environment for auto-detection:

```python
async with RekkoClient() as client:
    markets = await client.list_markets()
```

Or use the x402 httpx transport directly:

```python
from x402 import x402Client
from x402.mechanisms.evm.exact.client import ExactEvmScheme
from x402.http.clients.httpx import wrapHttpxWithPayment
from x402.http.x402_http_client import x402HTTPClient
from eth_account import Account

signer = Account.from_key("0x<your-private-key>")
scheme = ExactEvmScheme(signer)
x402c = x402Client()
x402c.register("eip155:8453", scheme)
http = wrapHttpxWithPayment(x402HTTPClient(x402c), base_url="https://api.rekko.ai")

resp = await http.get("/v1/markets")  # 402 -> sign -> retry handled automatically
```

**Network**: `eip155:8453` (Base mainnet). Payment is in USDC (6 decimals).

### Local MCP (for Claude Code, Cursor, OpenClaw)

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "rekko": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rekko-ai", "python", "-m", "rekko_server.mcp"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "GOOGLE_API_KEY": "AIza..."
      }
    }
  }
}
```

MCP local mode includes additional tools not available via the HTTP API: `search_markets`, `place_shadow_trade`, `get_portfolio`, `check_resolutions`, `run_scraper`, `get_calibration`.

## Pricing

Check `/v1/pricing` for current rates. Tier pricing (x402 USDC on Base):

| Tier | Price | Endpoints |
|---|---|---|
| Free | $0.00 | `/v1/calibration`, `/v1/pricing`, `/v1/health` |
| Listing | $0.01 | `/v1/markets`, `/v1/markets/{platform}/{market_id}`, `/v1/markets/{platform}/{market_id}/history`, `/v1/stream` |
| Insight | $0.10 | `/v1/analyses`, `/v1/markets/{platform}/{market_id}/analysis`, `/v1/markets/{platform}/{market_id}/analyze`, `/v1/screen`, `/v1/markets/{platform}/{market_id}/resolution` |
| Strategy | $2.00 | `/v1/signals`, `/v1/signals/portfolio`, `/v1/markets/{platform}/{market_id}/execution`, `/v1/trades/report`, `/v1/markets/{platform}/{market_id}/consensus` |
| Deep | $5.00 | `/v1/arbitrage`, `/v1/arbitrage/live`, `/v1/correlation`, `/v1/webhooks` |

## Endpoints

### Free (no auth required)

| Endpoint | Method | Description |
|---|---|---|
| `/v1/health` | GET | Health check with data freshness metrics |
| `/v1/pricing` | GET | Current tier pricing for all endpoints |
| `/v1/calibration` | GET | Signal accuracy and calibration metrics (Brier score, hit rates) |

### Market Intelligence (Listing tier)

| Endpoint | Method | Description | Key Parameters |
|---|---|---|---|
| `/v1/markets` | GET | Browse current prediction markets | `source` ("kalshi"/"polymarket"/"robinhood"/""), `limit` (1-100) |
| `/v1/markets/{platform}/{market_id}` | GET | Single market detail | `expand` (e.g. "analysis") |
| `/v1/markets/{platform}/{market_id}/history` | GET | Price history | `period` ("48h"/"7d"/"30d"), `max_points` |

### Screening & Discovery (Insight tier)

| Endpoint | Method | Description | Key Parameters |
|---|---|---|---|
| `/v1/analyses` | GET | List recent analyses | `limit` (1-50) |
| `/v1/markets/{platform}/{market_id}/analysis` | GET | Latest analysis for a market | `expand` (e.g. "scenarios,causal") |
| `/v1/markets/{platform}/{market_id}/analyze` | POST | Trigger async analysis (returns analysis_id) | — |
| `/v1/markets/{platform}/{market_id}/analyze/{analysis_id}/status` | GET | Poll analysis status | — |
| `/v1/screen` | POST | Batch screen markets by score/volume | `market_ids[]`, `platform`, `min_volume_24h`, `min_score`, `limit` |
| `/v1/markets/{platform}/{market_id}/resolution` | GET | Resolution intelligence (time urgency, mechanism, theta) | — |

### Strategy (Strategy tier)

| Endpoint | Method | Description | Key Parameters |
|---|---|---|---|
| `/v1/signals` | POST | Generate AI strategy signal | `market_query`, `market_id`, `platform`, `force`, `?wait=true`, `?expand=causal` |
| `/v1/signals/portfolio` | POST | Portfolio-aware signal with correlation analysis | `market_query`, `portfolio[]`, `bankroll_usd`, `max_position_pct` |
| `/v1/markets/{platform}/{market_id}/execution` | GET | Execution guidance (spread, slippage, timing) | — |
| `/v1/trades/report` | POST | Report a trade for consensus aggregation | `market_id`, `platform`, `side`, `size_usd`, `price` |
| `/v1/markets/{platform}/{market_id}/consensus` | GET | Consensus probability from agent trades | `period` ("24h"/"7d"/"30d") |

### Deep Intelligence (Deep tier)

| Endpoint | Method | Description | Key Parameters |
|---|---|---|---|
| `/v1/arbitrage` | GET | Cross-platform arb opportunities (cached) | `min_spread` (0.0-0.5) |
| `/v1/arbitrage/live` | GET | Fresh arbitrage scan (10-30s) | `min_spread` |
| `/v1/correlation` | POST | Cross-market correlation graph | `market_ids[]`, `platform`, `period` |
| `/v1/webhooks` | POST | Register webhook for real-time events | `url`, `events[]`, `secret` |
| `/v1/webhooks` | GET | List registered webhooks | — |
| `/v1/webhooks/{webhook_id}` | DELETE | Remove a webhook | — |

### Streaming (Listing tier)

| Endpoint | Method | Description | Key Parameters |
|---|---|---|---|
| `/v1/stream` | GET | SSE real-time event stream | `events` ("price_shift,whale_alert,analysis_complete") |

### Analytics (authenticated)

| Endpoint | Method | Description | Key Parameters |
|---|---|---|---|
| `/v1/sentiment` | GET | Market sentiment snapshot (fear/greed, regime, top movers) | — |
| `/v1/performance` | GET | Trading track record (win rate, P&L, ROI) | `mode` ("shadow"/"live") |
| `/v1/performance/history` | GET | Daily P&L time series for equity curve | `mode` |

## Query Parameters

Several endpoints support optional query parameters:

- **`?expand=`** — comma-separated expansions to include additional data:
  - `causal` — include causal decomposition on signals and analyses
  - `scenarios` — include scenario analysis
  - `analysis` — embed latest analysis on market detail
  - `scoring` — include score component breakdown on arbitrage
  - `meta` — include metadata
  - `history` — include price history
- **`?wait=true`** — on `POST /v1/signals`, blocks until the pipeline completes (30-90s) instead of returning 202
- **`?force=true`** — on `POST /v1/signals`, bypass the 24h analysis cache

## Interpreting Responses

### Recommendation

The `recommendation` field in signal responses uses these values:

- **`BUY_YES`** — market underprices the YES outcome, buy YES contracts
- **`BUY_NO`** — market overprices the YES outcome, buy NO contracts
- **`NO_TRADE`** — no actionable edge detected

### Edge

`edge = estimated_probability - market_price`

- **Positive edge** means the market underprices YES (potential BUY_YES)
- **Negative edge** means the market overprices YES (potential BUY_NO)
- Magnitude indicates signal strength (e.g. +0.12 = 12 percentage points of estimated mispricing)

### Confidence

`confidence` ranges from 0.0 to 1.0:

- **0.0 - 0.3** — low confidence, limited data or high uncertainty
- **0.3 - 0.6** — moderate confidence, reasonable evidence base
- **0.6 - 0.8** — high confidence, strong evidence
- **0.8 - 1.0** — very high confidence, near-certain factors identified

### Causal Decomposition

Strategy signals include a `causal` object (via `?expand=causal`). Each factor has:

- **`claim`** — the factor statement
- **`direction`** — `supports_yes`, `supports_no`, or `neutral`
- **`weight`** — relative importance (top-level factors sum to ~1.0)
- **`prior`** — base rate probability before evidence
- **`posterior`** — updated probability after evidence
- **`evidence`** — source references supporting this factor

### Arb Score

Arbitrage opportunities include a `score` from 0 to 100:

- **0-30** — minor spread, may not cover fees
- **30-60** — moderate opportunity, worth monitoring
- **60-80** — strong opportunity, actionable
- **80-100** — exceptional spread with good liquidity

The score is a weighted composite: 40% spread magnitude, 20% liquidity, 20% match confidence, 20% execution feasibility.

### Screen Result

`screen` returns scored markets with:

- **`score`** — composite of volume, movement, and signal quality
- **`action`** — `"analyze"` (worth a strategy call), `"watch"` (monitor for movement), or `"skip"` (low value)

Use this to filter before calling the more expensive `/v1/signals` endpoint.

### Execution Guidance

`execution` returns order execution advice:

- **`recommendation`** — `"LIMIT_ORDER"`, `"MARKET_ORDER"`, or `"WAIT"`
- **`current_spread`** — current bid-ask spread
- **`estimated_slippage_pct`** — expected slippage for a typical order size
- **`rationale`** — context on liquidity patterns

### Resolution Intelligence

`resolution` returns settlement timing context:

- **`time_urgency`** — `"critical"` (< 24h), `"high"` (1-3d), `"medium"` (3-14d), `"low"` (> 14d)
- **`resolution_mechanism`** — how the market resolves (e.g. "scheduled_data_release", "event_outcome")
- **`theta_estimate`** — estimated daily time decay rate

### Consensus View

`consensus` aggregates trades reported by agents:

- **`consensus_probability`** — weighted average probability from reported trades
- **`sample_size`** — number of trades aggregated
- **`divergence_signal`** — `"crowd_agrees"`, `"crowd_disagrees"`, `"strong_divergence"`, or `"neutral"`

### Correlation Graph

`correlation` returns pairwise relationships:

- **`pairs`** — list of `{market_a, market_b, correlation, relationship}` entries
- **`clusters`** — groups of correlated markets
- **`concentration_warnings`** — alerts if your requested markets are highly correlated

### Calibration Metrics

`calibration` returns signal accuracy data:

- **`brier_score`** — lower is better (0.0 = perfect, 0.25 = random)
- **`confidence_buckets`** — hit rate grouped by confidence level
- **`total_signals`** — number of signals in the measurement period

## Workflow Patterns

### Pattern A: Research then Execute

An agent spots an interesting market, uses Rekko for analysis, then chains to an execution skill.

```
1. GET /v1/markets?source=kalshi&limit=30
2. POST /v1/signals { "market_query": "Will the Fed cut rates?", "platform": "kalshi" } ?wait=true&expand=causal
3. IF recommendation == "BUY_YES" AND confidence > 0.5:
     -> chain to Kalshi Trader: buy YES at target_price with size_pct of bankroll
```

### Pattern B: Arbitrage Discovery then Execution

```
1. GET /v1/arbitrage?min_spread=0.03
2. FOR each opportunity with score > 60:
     a. Buy YES on the cheaper platform via the appropriate execution skill
     b. POST /v1/trades/report to track for consensus
3. GET /v1/performance periodically to review track record
```

### Pattern C: Smart Screening

Use batch screening to find markets worth analyzing, then run strategy only on high-score candidates:

```
1. POST /v1/screen { "platform": "kalshi", "min_volume_24h": 50000, "min_score": 50, "limit": 50 }
2. FOR each result WHERE action == "analyze":
     POST /v1/signals { "market_id": result.market_id, "platform": "kalshi" } ?wait=true
3. IF recommendation != "NO_TRADE" AND confidence > 0.5:
     -> execute via Kalshi Trader or PolyClaw
```

This saves 80-90% on strategy costs by filtering out low-value markets first.

### Pattern D: Portfolio-Aware Trading

Use portfolio context to avoid concentration and size positions correctly:

```
1. POST /v1/signals/portfolio {
     "market_query": "Will Bitcoin hit 100K by June?",
     "portfolio": [{"platform": "kalshi", "market_id": "KXBTC-100K", "side": "yes", "size_usd": 250, "entry_price": 0.40}],
     "bankroll_usd": 10000,
     "max_position_pct": 0.05
   }
2. IF recommendation != "NO_TRADE":
     POST /v1/correlation { "market_ids": [new_market, ...existing_ids], "platform": "kalshi" }
     IF concentration_warnings is empty:
       -> execute trade
```

### Pattern E: Consensus-Enhanced Trading

Report your trades and check whether the crowd agrees:

```
1. POST /v1/signals { "market_query": "Will unemployment rise above 4.5?" } ?wait=true
2. IF recommendation == "BUY_YES":
     -> execute trade
     POST /v1/trades/report { "market_id": "KXUNEMP-4.5", "platform": "kalshi", "side": "yes", "size_usd": 100, "price": 0.45 }
3. LATER:
     GET /v1/markets/kalshi/KXUNEMP-4.5/consensus?period=7d
     IF divergence_signal == "crowd_agrees": log("Mispricing likely real")
     IF divergence_signal == "crowd_disagrees": log("Reconsider position")
```

### Pattern F: Real-Time Monitoring

Use SSE streaming for live alerts, webhooks for fire-and-forget:

```
# Option 1: SSE stream (agent stays connected)
GET /v1/stream?events=whale_alert,price_shift
  ON whale_alert: POST /v1/signals { "market_query": event.title } ?wait=true
  ON price_shift > 5%: GET /v1/markets/{platform}/{market_id}/execution

# Option 2: Webhooks (async, agent receives POSTs)
POST /v1/webhooks { "url": "https://my-agent.com/hook", "events": ["whale_alert", "analysis_complete"] }
```

## x402 Payment Flow

When x402 is enabled, the payment handshake works as follows:

```
Agent                           Rekko Feed API
  |                                    |
  |  GET /v1/markets                   |
  |  --------------------------------> |
  |                                    |
  |  402 Payment Required              |
  |  payment-required: <base64 JSON>   |
  |  <-------------------------------- |
  |                                    |
  |  [sign USDC EIP-712 payment]       |
  |                                    |
  |  GET /v1/markets                   |
  |  payment-signature: <signed proof> |
  |  --------------------------------> |
  |                                    |
  |  [facilitator verifies + settles]  |
  |                                    |
  |  200 OK                            |
  |  [market data]                     |
  |  <-------------------------------- |
```

The `x402` Python package handles this loop automatically when you use `RekkoClient(signer=...)` or `wrapHttpxWithPayment()`. No manual header parsing needed.

## Risk Limits

When using Rekko signals for trading, enforce these guardrails:

- **Max 5% of bankroll per position** — even when `size_pct` is higher
- **Shadow trade before live** — validate the strategy with paper trades first
- **Never trade without edge** — if `recommendation` is `NO_TRADE`, respect it
- **Check freshness** — strategy signals have an `expires_at` timestamp; do not trade stale signals
- **Diversify with correlation** — use `/v1/correlation` to check for concentration risk before adding positions
- **Check execution guidance** — call `/v1/markets/{platform}/{market_id}/execution` before placing large orders to avoid slippage
- **Respect consensus divergence** — if `divergence_signal` is `"crowd_disagrees"`, reconsider your position
- **Check calibration periodically** — use `/v1/calibration` to verify signal accuracy before trusting high-confidence calls
