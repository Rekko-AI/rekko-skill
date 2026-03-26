# Rekko Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Prediction market intelligence skill for AI agents. Deep causal research, arbitrage detection, screening, and strategy signals for **Kalshi**, **Polymarket**, and **Robinhood**.

## What is Rekko?

In the OpenClaw ecosystem, three skills work together for autonomous prediction market trading:

| Skill | Role | What it does |
|-------|------|-------------|
| **Rekko** (this skill) | The Brain | Deep causal research, probability estimates, trading signals |
| **PolyClaw** | The Hands (Polymarket) | Executes trades on Polymarket via CTF minting + CLOB |
| **Kalshi Trader** | The Hands (Kalshi) | Executes trades on Kalshi |

Rekko provides the *why* behind market movements. Execution skills handle the *how*.

## Install

```bash
npx skills add Rekko-AI/rekko-skill
```

Or copy `SKILL.md` directly into your agent's skill directory.

## Authentication

Two options:

### API key (simple)

Get a key at [rekko.ai](https://rekko.ai/dashboard), then set:

```bash
export REKKO_API_KEY=rk_free_your_key_here
```

### x402 autopay (for autonomous agents)

Fund an EVM wallet with USDC on Base mainnet, then use the included Python client:

```python
from eth_account import Account
from rekko_tools import RekkoClient

signer = Account.from_key("0x<your-private-key>")
async with RekkoClient(signer=signer) as client:
    markets = await client.list_markets()
    signal = await client.get_strategy("Will the Fed cut rates?")
```

Or set `X402_PRIVATE_KEY` in your environment for auto-detection.

## Python client

Install dependencies:

```bash
pip install -r requirements.txt
```

The `rekko_tools.py` module provides `RekkoClient` — an async HTTP client with x402 payment support:

```python
from rekko_tools import RekkoClient

async with RekkoClient() as client:
    # Browse markets ($0.01/call)
    markets = await client.list_markets(source="kalshi", limit=30)

    # Screen for high-value candidates ($0.10/call)
    screened = await client.screen_markets(platform="kalshi", min_score=50)

    # Deep analysis with strategy signal ($2.00/call)
    signal = await client.get_strategy("Will Bitcoin hit 100K by June?")

    # Cross-platform arbitrage scan ($5.00/call)
    arbs = await client.get_arbitrage(min_spread=0.03)
```

## Example workflow

```
1. list_markets(source="kalshi", limit=30)
2. screen_markets(platform="kalshi", min_volume_24h=50000, min_score=50)
3. get_strategy(market_query="Will the Fed cut rates?")
4. IF recommendation == "BUY_YES" AND confidence > 0.5:
     -> chain to Kalshi Trader or PolyClaw for execution
5. place_shadow_trade(ticker, side, size_usd)  # track in Rekko portfolio
```

See `SKILL.md` for all 6 workflow patterns, complete endpoint reference, and response interpretation guide.

## Links

- [rekko.ai/docs](https://rekko.ai/docs) — Full documentation
- [OpenClaw integration guide](https://rekko.ai/docs/integrations/openclaw/overview) — Detailed setup
- [API Reference](https://rekko.ai/docs/api-reference/introduction) — Direct API access
- [Discord](https://discord.gg/qTPEk9aAZg) — Community
