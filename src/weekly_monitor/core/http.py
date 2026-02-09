"""Shared HTTP client with retries, backoff, timeouts, and UA header."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_TIMEOUT = httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0)


def build_client(*, accept_language: str = "", **kwargs: Any) -> httpx.Client:
    """Return a pre-configured httpx.Client.

    Parameters
    ----------
    accept_language:
        If set (e.g. ``"en"``), sends an ``Accept-Language`` header so the
        remote server returns content in the requested language.
    """
    extra_headers = kwargs.pop("headers", {})
    headers = {"User-Agent": USER_AGENT, **extra_headers}
    if accept_language:
        headers["Accept-Language"] = accept_language
    return httpx.Client(
        headers=headers,
        timeout=_TIMEOUT,
        follow_redirects=True,
        **kwargs,
    )


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def fetch_url(url: str, client: httpx.Client | None = None) -> httpx.Response:
    """GET *url* with automatic retry + backoff."""
    own_client = client is None
    if own_client:
        client = build_client()
    try:
        logger.info("GET %s", url)
        resp = client.get(url)
        resp.raise_for_status()
        return resp
    finally:
        if own_client:
            client.close()


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def fetch_json(url: str, client: httpx.Client | None = None) -> Any:
    """GET *url* and return decoded JSON."""
    own_client = client is None
    if own_client:
        client = build_client()
    try:
        logger.info("GET (json) %s", url)
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()
    finally:
        if own_client:
            client.close()
