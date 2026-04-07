"""Rekko tools -- x402-aware httpx client for the Feed API.

This module provides an async client for the Rekko AI Feed API.
Authentication is via x402 autopay — the client automatically handles
402 → sign → retry with USDC on Base. No account or key management needed.

Set ``X402_PRIVATE_KEY`` in the environment (hex EVM private key) and the
client auto-detects it, or pass a ``signer`` to the constructor.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

import httpx

logger = logging.getLogger(__name__)

REKKO_API_BASE = "https://api.rekko.ai"


def _make_x402_client(
    signer: Any,
    network: str = "eip155:8453",
    **httpx_kwargs: Any,
) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient that handles x402 payments automatically.

    Args:
        signer: An EVM signer — either an ``eth_account.LocalAccount`` or
            a ``ClientEvmSigner`` from the x402 package.
        network: CAIP-2 network ID. Default is Base mainnet (eip155:8453).
        **httpx_kwargs: Extra kwargs passed to ``httpx.AsyncClient``.

    Returns:
        An ``httpx.AsyncClient`` that intercepts 402 responses, signs the
        USDC payment, and retries automatically.
    """
    from x402 import x402Client
    from x402.http.clients.httpx import wrapHttpxWithPayment
    from x402.http.x402_http_client import x402HTTPClient
    from x402.mechanisms.evm.exact.client import ExactEvmScheme

    scheme = ExactEvmScheme(signer)
    client = x402Client()
    client.register(network, scheme)
    http_client = x402HTTPClient(client)

    return wrapHttpxWithPayment(http_client, **httpx_kwargs)


class RekkoClient:
    """Async client for the Rekko AI Feed API with x402 payment support.

    Usage with x402 autopay (recommended):

        from eth_account import Account
        signer = Account.from_key("0x...")
        client = RekkoClient(signer=signer)
        markets = await client.list_markets()
        await client.close()

    Usage as async context manager:

        async with RekkoClient(signer=signer) as client:
            markets = await client.list_markets()

    Or set X402_PRIVATE_KEY in env for auto-detection:

        async with RekkoClient() as client:
            markets = await client.list_markets()
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        signer: Any = None,
        network: str = "eip155:8453",
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url or os.environ.get("REKKO_API_URL", REKKO_API_BASE)
        self.api_key = api_key or os.environ.get("REKKO_API_KEY", "")

        # Auto-detect x402 signer from env if no signer or API key provided
        if signer is None and not self.api_key:
            x402_key = os.environ.get("X402_PRIVATE_KEY", "")
            if x402_key:
                from eth_account import Account

                if not x402_key.startswith("0x"):
                    x402_key = f"0x{x402_key}"
                signer = Account.from_key(x402_key)

        if signer is not None:
            # x402 autopay — httpx transport handles 402 retry loop
            self._client = _make_x402_client(
                signer,
                network=network,
                base_url=self.base_url,
                timeout=timeout,
            )
        else:
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=timeout,
            )

    # -----------------------------------------------------------------
    # Market intelligence
    # -----------------------------------------------------------------

    async def list_markets(
        self, source: str = "", limit: int = 30
    ) -> dict[str, Any]:
        """List current prediction markets.

        Args:
            source: Filter by platform: "kalshi", "polymarket", or "" for all.
            limit: Maximum number of markets to return (1-100).
        """
        params: dict[str, Any] = {"limit": limit}
        if source:
            params["source"] = source
        return await self._request("GET", "/v1/markets", params=params)

    async def get_market(
        self, platform: str, market_id: str, expand: str = ""
    ) -> dict[str, Any]:
        """Get details for a single market.

        Args:
            platform: "kalshi" or "polymarket".
            market_id: Platform-specific identifier (ticker or slug).
            expand: Comma-separated expansions (e.g. "analysis").
        """
        params: dict[str, str] = {}
        if expand:
            params["expand"] = expand
        return await self._request(
            "GET", f"/v1/markets/{platform}/{market_id}", params=params
        )

    async def get_market_history(
        self,
        platform: str,
        market_id: str,
        period: str = "7d",
        max_points: int = 48,
    ) -> dict[str, Any]:
        """Get price history for a market.

        Args:
            platform: "kalshi" or "polymarket".
            market_id: Platform-specific identifier (ticker or slug).
            period: Time window -- "48h", "7d", or "30d".
            max_points: Maximum number of data points to return.
        """
        params: dict[str, Any] = {"period": period, "max_points": max_points}
        return await self._request(
            "GET", f"/v1/markets/{platform}/{market_id}/history", params=params
        )

    async def get_resolution(
        self, platform: str, market_id: str
    ) -> dict[str, Any]:
        """Get resolution intelligence for a market."""
        return await self._request(
            "GET", f"/v1/markets/{platform}/{market_id}/resolution"
        )

    async def get_execution_guidance(
        self, platform: str, market_id: str
    ) -> dict[str, Any]:
        """Get execution guidance for a market (spread, slippage, timing)."""
        return await self._request(
            "GET", f"/v1/markets/{platform}/{market_id}/execution"
        )

    # -----------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------

    async def list_events(
        self, source: str = "", category: str = "", featured: bool | None = None, limit: int = 20
    ) -> dict[str, Any]:
        """List prediction market events with aggregate stats.

        Args:
            source: Filter by platform: "kalshi", "polymarket", or "" for all.
            category: Filter by category (e.g. "politics", "crypto") or "" for all.
            featured: Only featured events (true) or all (None).
            limit: Maximum number of events to return (1-100).
        """
        params: dict[str, Any] = {"limit": limit}
        if source:
            params["source"] = source
        if category:
            params["category"] = category
        if featured is not None:
            params["featured"] = featured
        return await self._request("GET", "/v1/events", params=params)

    async def trending_events(self, limit: int = 20) -> dict[str, Any]:
        """Get top trending prediction market events.

        Args:
            limit: Maximum number of trending events to return (1-50).
        """
        return await self._request(
            "GET", "/v1/events/trending", params={"limit": limit}
        )

    async def search_events(self, query: str, limit: int = 20) -> dict[str, Any]:
        """Search prediction market events using hybrid full-text + semantic search.

        Args:
            query: Search query (supports semantic + keyword matching).
            limit: Maximum number of results to return (1-50).
        """
        return await self._request(
            "GET", "/v1/events/search", params={"q": query, "limit": limit}
        )

    async def get_event(
        self, slug: str, expand: str = ""
    ) -> dict[str, Any]:
        """Get detailed information about a single prediction market event.

        Args:
            slug: Event slug (e.g. 'kalshi:kxtrumpadminleave-26dec31').
            expand: Comma-separated expansions (e.g. "markets").
        """
        params: dict[str, str] = {}
        if expand:
            params["expand"] = expand
        return await self._request("GET", f"/v1/events/{slug}", params=params)

    async def get_event_markets(self, slug: str) -> dict[str, Any]:
        """List all individual outcome markets within an event.

        Args:
            slug: Event slug (e.g. 'kalshi:kxtrumpadminleave-26dec31').
        """
        return await self._request("GET", f"/v1/events/{slug}/markets")

    async def analyze_event(self, slug: str) -> dict[str, Any]:
        """Trigger an AI analysis of an entire event (all sub-markets).

        Returns an analysis_id for polling. The analysis covers the event
        holistically — ranking sub-markets, identifying surprises, and
        producing a probability map.

        Args:
            slug: Event slug (e.g. 'kalshi:kxtrumpadminleave-26dec31').
        """
        return await self._request("POST", f"/v1/events/{slug}/analyze")

    async def get_event_analysis(
        self, slug: str, expand: str = ""
    ) -> dict[str, Any]:
        """Get the latest AI analysis for an event.

        Args:
            slug: Event slug (e.g. 'kalshi:kxtrumpadminleave-26dec31').
            expand: Comma-separated expansions (e.g. "scenarios,causal").
        """
        params: dict[str, str] = {}
        if expand:
            params["expand"] = expand
        return await self._request(
            "GET", f"/v1/events/{slug}/analysis", params=params
        )

    async def get_event_probability_map(self, slug: str) -> dict[str, Any]:
        """Get probability estimates for all sub-markets within an event.

        Returns a map of market_id → probability with confidence intervals,
        useful for comparing outcomes within a single event.

        Args:
            slug: Event slug (e.g. 'kalshi:kxtrumpadminleave-26dec31').
        """
        return await self._request(
            "GET", f"/v1/events/{slug}/probability-map"
        )

    async def get_event_correlation(self, slug: str) -> dict[str, Any]:
        """Get cross-market correlation analysis within an event.

        Identifies which sub-markets within the event move together,
        concentration risks, and hedge opportunities.

        Args:
            slug: Event slug (e.g. 'kalshi:kxtrumpadminleave-26dec31').
        """
        return await self._request(
            "GET", f"/v1/events/{slug}/correlation"
        )

    # -----------------------------------------------------------------
    # Screening & discovery
    # -----------------------------------------------------------------

    async def screen_markets(
        self,
        market_ids: list[str] | None = None,
        platform: str = "",
        min_volume_24h: float = 0,
        min_score: float = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Batch screen markets by score, volume, or explicit IDs."""
        body: dict[str, Any] = {"limit": limit}
        if market_ids:
            body["market_ids"] = market_ids
        if platform:
            body["platform"] = platform
        if min_volume_24h > 0:
            body["min_volume_24h"] = min_volume_24h
        if min_score > 0:
            body["min_score"] = min_score
        return await self._request("POST", "/v1/screen", json=body)

    async def get_calibration(
        self,
        category: str = "",
        period: str = "all",
        mode: str = "shadow",
    ) -> dict[str, Any]:
        """Get signal accuracy and calibration metrics. No auth required."""
        params: dict[str, Any] = {"period": period, "mode": mode}
        if category:
            params["category"] = category
        return await self._request("GET", "/v1/calibration", params=params)

    # -----------------------------------------------------------------
    # Real-time signals
    # -----------------------------------------------------------------

    def stream_events(
        self, events: str = ""
    ) -> AsyncIterator[httpx.Response]:
        """Connect to the SSE real-time event stream."""
        params: dict[str, str] = {}
        if events:
            params["events"] = events
        return self._client.stream("GET", "/v1/stream", params=params)

    # -----------------------------------------------------------------
    # Webhooks
    # -----------------------------------------------------------------

    async def create_webhook(
        self, url: str, events: list[str], secret: str = ""
    ) -> dict[str, Any]:
        """Register a webhook for async event notifications."""
        body: dict[str, Any] = {"url": url, "events": events}
        if secret:
            body["secret"] = secret
        return await self._request("POST", "/v1/webhooks", json=body)

    async def list_webhooks(self) -> dict[str, Any]:
        """List all registered webhooks."""
        return await self._request("GET", "/v1/webhooks")

    async def delete_webhook(self, webhook_id: str) -> dict[str, Any]:
        """Delete a registered webhook."""
        return await self._request("DELETE", f"/v1/webhooks/{webhook_id}")

    # -----------------------------------------------------------------
    # Deep research (async pattern)
    # -----------------------------------------------------------------

    async def analyze_market(
        self, platform: str, market_id: str
    ) -> dict[str, Any]:
        """Start an async analysis pipeline for a market.

        Returns immediately with an analysis_id for polling.

        Args:
            platform: "kalshi" or "polymarket".
            market_id: Platform-specific identifier.
        """
        return await self._request(
            "POST", f"/v1/markets/{platform}/{market_id}/analyze"
        )

    async def check_analysis_status(
        self, platform: str, market_id: str, analysis_id: str
    ) -> dict[str, Any]:
        """Check whether an async analysis has completed.

        Args:
            platform: "kalshi" or "polymarket".
            market_id: Platform-specific identifier.
            analysis_id: ID returned by analyze_market.
        """
        return await self._request(
            "GET",
            f"/v1/markets/{platform}/{market_id}/analyze/{analysis_id}/status",
        )

    async def get_analysis(
        self, platform: str, market_id: str, expand: str = ""
    ) -> dict[str, Any]:
        """Get the latest analysis for a market.

        Args:
            platform: "kalshi" or "polymarket".
            market_id: Platform-specific identifier.
            expand: Comma-separated expansions (e.g. "scenarios,causal").
        """
        params: dict[str, str] = {}
        if expand:
            params["expand"] = expand
        return await self._request(
            "GET", f"/v1/markets/{platform}/{market_id}/analysis", params=params
        )

    async def list_analyses(self, limit: int = 20) -> dict[str, Any]:
        """List recent analyses with summary information.

        Args:
            limit: Maximum number of analyses to return (1-50).
        """
        return await self._request(
            "GET", "/v1/analyses", params={"limit": limit}
        )

    # -----------------------------------------------------------------
    # Strategy & portfolio
    # -----------------------------------------------------------------

    async def get_strategy(
        self,
        market_query: str = "",
        platform: str = "",
        market_id: str = "",
        force: bool = False,
        wait: bool = True,
        expand: str = "",
    ) -> dict[str, Any]:
        """Generate a strategy signal for a market.

        By default blocks until the pipeline completes (30-90s).
        Set wait=False for async mode (returns 202 with analysis_id).

        Args:
            market_query: Free-text market question (used if market_id not set).
            platform: "kalshi" or "polymarket".
            market_id: Platform-specific identifier.
            force: Bypass 24h analysis cache.
            wait: Block until complete (default True).
            expand: Comma-separated expansions (e.g. "causal").
        """
        body: dict[str, Any] = {}
        if market_query:
            body["market_query"] = market_query
        if platform:
            body["platform"] = platform
        if market_id:
            body["market_id"] = market_id
        if force:
            body["force"] = True

        params: dict[str, Any] = {}
        if wait:
            params["wait"] = "true"
        if expand:
            params["expand"] = expand

        return await self._request(
            "POST", "/v1/signals", json=body, params=params
        )

    async def get_portfolio_strategy(
        self,
        market_query: str,
        portfolio: list[dict[str, Any]] | None = None,
        bankroll_usd: float = 1000,
        max_position_pct: float = 0.10,
    ) -> dict[str, Any]:
        """Get a portfolio-aware strategy signal."""
        body: dict[str, Any] = {
            "market_query": market_query,
            "bankroll_usd": bankroll_usd,
            "max_position_pct": max_position_pct,
        }
        if portfolio is not None:
            body["portfolio"] = portfolio
        return await self._request("POST", "/v1/signals/portfolio", json=body)

    async def get_consensus(
        self,
        platform: str,
        market_id: str,
        period: str = "7d",
    ) -> dict[str, Any]:
        """Get consensus probability from aggregated agent trades."""
        params: dict[str, Any] = {"period": period}
        return await self._request(
            "GET",
            f"/v1/markets/{platform}/{market_id}/consensus",
            params=params,
        )

    async def what_if(
        self,
        market_query: str,
        hypothesis: str,
        platform: str = "",
    ) -> dict[str, Any]:
        """Analyze how a hypothetical scenario would affect a market's probability.

        Args:
            market_query: Market question, ticker, or URL.
            hypothesis: Hypothetical scenario to evaluate (e.g. "Fed cuts rates by 50bps").
            platform: Platform hint: "kalshi" or "polymarket".
        """
        body: dict[str, Any] = {
            "market_query": market_query,
            "hypothesis": hypothesis,
        }
        if platform:
            body["platform"] = platform
        return await self._request("POST", "/v1/what-if", json=body)

    # -----------------------------------------------------------------
    # Arbitrage
    # -----------------------------------------------------------------

    async def get_arbitrage(
        self, min_spread: float = 0.02
    ) -> dict[str, Any]:
        """Get cross-platform arbitrage opportunities (cached)."""
        return await self._request(
            "GET", "/v1/arbitrage", params={"min_spread": min_spread}
        )

    async def get_arbitrage_live(
        self, min_spread: float = 0.02
    ) -> dict[str, Any]:
        """Run a fresh arbitrage scan (may take 10-30s)."""
        return await self._request(
            "GET", "/v1/arbitrage/live", params={"min_spread": min_spread}
        )

    # -----------------------------------------------------------------
    # Correlation
    # -----------------------------------------------------------------

    async def get_correlation(
        self,
        market_ids: list[str],
        platform: str = "kalshi",
        period: str = "7d",
    ) -> dict[str, Any]:
        """Get cross-market correlation graph."""
        return await self._request(
            "POST",
            "/v1/correlation",
            json={
                "market_ids": market_ids,
                "platform": platform,
                "period": period,
            },
        )

    # -----------------------------------------------------------------
    # Consensus trading
    # -----------------------------------------------------------------

    async def report_trade(
        self,
        market_id: str,
        platform: str,
        side: str,
        size_usd: float,
        price: float,
    ) -> dict[str, Any]:
        """Report a trade for consensus aggregation."""
        return await self._request(
            "POST",
            "/v1/trades/report",
            json={
                "market_id": market_id,
                "platform": platform,
                "side": side,
                "size_usd": size_usd,
                "price": price,
            },
        )

    # -----------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------

    async def get_sentiment(self) -> dict[str, Any]:
        """Get market sentiment snapshot (fear/greed index, regime, top movers)."""
        return await self._request("GET", "/v1/sentiment")

    async def get_performance(self, mode: str = "shadow") -> dict[str, Any]:
        """Get aggregate trading performance statistics."""
        return await self._request(
            "GET", "/v1/performance", params={"mode": mode}
        )

    async def get_performance_history(
        self, mode: str = "shadow"
    ) -> dict[str, Any]:
        """Get daily P&L time series for equity curve charting."""
        return await self._request(
            "GET", "/v1/performance/history", params={"mode": mode}
        )

    # -----------------------------------------------------------------
    # Free endpoints (no auth required)
    # -----------------------------------------------------------------

    async def get_pricing(self) -> dict[str, Any]:
        """Get current tier pricing for all endpoints. No auth required."""
        return await self._request("GET", "/v1/pricing")

    async def get_health(self) -> dict[str, Any]:
        """Health check. No auth required."""
        return await self._request("GET", "/v1/health")

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make a request. x402 payment is handled by the transport layer."""
        resp = await self._client.request(method, path, **kwargs)

        if resp.status_code == 402:
            # No signer configured (or payment failed)
            payment_details = self._parse_payment_required(resp)
            return {
                "error": "payment_required",
                "status": 402,
                "detail": "x402 payment needed -- configure a signer (set X402_PRIVATE_KEY env var)",
                "payment": payment_details,
            }

        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    @staticmethod
    def _parse_payment_required(resp: httpx.Response) -> dict[str, Any]:
        """Extract x402 payment requirements from a 402 response."""
        import base64

        raw = resp.headers.get("payment-required", "")
        if raw:
            try:
                decoded = base64.b64decode(raw)
                return json.loads(decoded)
            except Exception:
                return {"raw": raw}

        return {}

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "RekkoClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
