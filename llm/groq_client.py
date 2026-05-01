"""
Async Groq client built on httpx.

Routes a PURPOSE to a model via llm.routes; on 429 or 5xx, retries once on
the fallback model in the same purpose tier. Exposes a single async
`complete(purpose, prompt, system, json_mode, ...)` entrypoint.

Pre-warming: at startup, hits each distinct primary model with a tiny
"ready" message to warm the connection pool + populate keep-alive sockets.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from core.logging import logger
from core.settings import settings
from llm.routes import (
    ALL_MODELS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    FALLBACK_MODEL,
    PRIMARY_MODEL,
    Purpose,
)


class GroqError(Exception):
    """Raised after fallback also fails."""


class GroqClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = httpx.AsyncClient(
            base_url=settings.GROQ_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        logger.info("groq.client_opened")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("groq.client_closed")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("GroqClient not connected. Call connect() first.")
        return self._client

    # ─── pre-warm ────────────────────────────────────────────────────────────

    async def prewarm(self) -> None:
        """Send a tiny ping to each model to warm sockets + verify auth."""
        tiny_msg = "Reply with the word ok"
        results = await asyncio.gather(
            *(self._raw_call(model, tiny_msg, system="You are concise.", max_tokens=4, temperature=0.0)
              for model in ALL_MODELS),
            return_exceptions=True,
        )
        ok = sum(1 for r in results if isinstance(r, str))
        failed = [
            (m, r) for m, r in zip(ALL_MODELS, results) if not isinstance(r, str)
        ]
        logger.info("groq.prewarmed", extra={"ok": ok, "failed": len(failed), "models": ALL_MODELS})
        for model, exc in failed:
            logger.warning(
                "groq.prewarm_failed",
                extra={"model": model, "exc_type": type(exc).__name__, "exc": str(exc)[:200]},
            )

    # ─── public completion API ──────────────────────────────────────────────

    async def complete(
        self,
        purpose: Purpose,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """
        Run a completion against the model for `purpose`. On 429 / 5xx, retry
        once on the fallback model. Returns the raw assistant text.
        """
        primary = PRIMARY_MODEL[purpose]
        fallback = FALLBACK_MODEL[purpose]
        temp = temperature if temperature is not None else DEFAULT_TEMPERATURE[purpose]
        toks = max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS[purpose]

        try:
            return await self._raw_call(
                primary, prompt, system, json_mode, temp, toks, timeout_seconds
            )
        except _RetryableGroqError as e:
            logger.warning(
                "groq.fallback",
                extra={
                    "purpose": purpose.value,
                    "primary": primary,
                    "fallback": fallback,
                    "reason": str(e)[:200],
                },
            )
            return await self._raw_call(
                fallback, prompt, system, json_mode, temp, toks, timeout_seconds
            )

    # ─── internals ───────────────────────────────────────────────────────────

    async def _raw_call(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 600,
        timeout_seconds: float | None = None,
    ) -> str:
        if self._client is None:
            await self.connect()

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        t0 = time.time()
        try:
            req_timeout = (
                httpx.Timeout(timeout_seconds) if timeout_seconds else None
            )
            r = await self.client.post(
                "/chat/completions",
                json=body,
                timeout=req_timeout if req_timeout else self.client.timeout,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            raise _RetryableGroqError(f"network/timeout: {e}") from e

        latency_ms = int((time.time() - t0) * 1000)

        if r.status_code == 429:
            raise _RetryableGroqError(f"rate_limited: {r.text[:200]}")
        if 500 <= r.status_code < 600:
            raise _RetryableGroqError(f"server_error_{r.status_code}: {r.text[:200]}")
        if r.status_code != 200:
            raise GroqError(f"http_{r.status_code}: {r.text[:300]}")

        try:
            data = r.json()
        except json.JSONDecodeError as e:
            raise GroqError(f"non_json_response: {e}") from e

        try:
            content: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise GroqError(f"malformed_response: {data}") from e

        logger.info(
            "groq.complete",
            extra={
                "model": model,
                "latency_ms": latency_ms,
                "input_tokens": data.get("usage", {}).get("prompt_tokens"),
                "output_tokens": data.get("usage", {}).get("completion_tokens"),
                "json_mode": json_mode,
            },
        )
        return content


class _RetryableGroqError(Exception):
    """Internal — triggers fallback to the secondary model."""


# Module-level singleton — initialized in bot.py lifespan
_singleton: GroqClient | None = None


def get_groq() -> GroqClient:
    global _singleton
    if _singleton is None:
        _singleton = GroqClient()
    return _singleton
