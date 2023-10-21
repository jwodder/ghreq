"""
Minimal yet well-configured GitHub API client

Visit <https://github.com/jwodder/ghreq> for more information.
"""

from __future__ import annotations
from collections.abc import Container, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import platform
from random import random
from time import sleep, time
from types import TracebackType
from typing import TYPE_CHECKING, Any
import requests

__version__ = "0.1.0.dev1"
__author__ = "John Thorvald Wodder II"
__author_email__ = "ghreq@varonathe.org"
__license__ = "MIT"
__url__ = "https://github.com/jwodder/ghreq"

__all__ = [
    "GitHub",
    "PrettyHTTPError",
    "RetryConfig",
    "get_github_api_url",
    "make_user_agent",
]

log = logging.getLogger(__name__)

DEFAULT_API_URL = "https://api.github.com"

MUTATING_METHODS = frozenset(["POST", "PATCH", "PUT", "DELETE"])

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    ParamsValue: TypeAlias = (
        str | bytes | int | float | Iterable[str | bytes | int | float] | None
    )
    ParamsType: TypeAlias = Mapping[str, ParamsValue] | None
    HeadersType: TypeAlias = Mapping[str, str | bytes | None] | None


class GitHub:
    def __init__(
        self,
        *,
        token: str | None,
        api_url: str = DEFAULT_API_URL,
        session: requests.Session | None = None,
        user_agent: str | None = None,
        mutation_delay: float = 1.0,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self.api_url = api_url
        if session is None:
            session = requests.Session()
            session.headers["Accept"] = "application/vnd.github+json"
            if token is not None:
                session.headers["Authorization"] = f"Bearer {token}"
            if user_agent is not None:
                session.headers["User-Agent"] = user_agent
            session.headers["X-GitHub-Api-Version"] = "2022-11-28"
        # No headers are set on pre-supplied sessions
        self.session = session
        # GitHub recommends waiting 1 second between non-GET requests in order
        # to avoid hitting secondary rate limits.
        self.mutation_delay = mutation_delay
        if retry_config is None:
            retry_config = RetryConfig()
        self.retry_config = retry_config
        self.last_mutation: datetime | None = None

    def __enter__(self) -> GitHub:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        self.session.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        json: Any = None,
        data: bytes | None = None,
        raw: bool = False,
    ) -> Any:
        if path.lower().startswith(("http://", "https://")):
            url = path
        else:
            url = self.api_url.rstrip("/") + "/" + path.lstrip("/")
        method = method.upper()
        log.debug("%s %s", method, url)
        if method in MUTATING_METHODS:
            mutdelay = self.mutation_delay
            if self.last_mutation is not None:
                mutdelay -= (nowdt() - self.last_mutation).total_seconds()
            if mutdelay > 0:
                log.debug("Sleeping for %f seconds between mutating requests", mutdelay)
                sleep(mutdelay)
        req = self.session.prepare_request(
            requests.Request(
                method, url, params=params, headers=headers, json=json, data=data
            )
        )
        retrier = Retrier(self.retry_config)
        try:
            while True:
                try:
                    if method in MUTATING_METHODS:
                        self.last_mutation = nowdt()
                    r = self.session.send(req)
                    r.raise_for_status()
                    break
                except ValueError:
                    # The errors that requests raises when the user supplies
                    # bad parameters all inherit ValueError
                    raise
                except requests.RequestException as e:
                    if (delay := retrier(e.response)) is not None:
                        if isinstance(e, requests.HTTPError) and e.response is not None:
                            log.warning(
                                "Server returned %d response; waiting %f"
                                " seconds and retrying",
                                e.response.status_code,
                                delay,
                            )
                        else:
                            log.warning(
                                "Request failed: %s: %s; waiting %f seconds and"
                                " retrying",
                                type(e).__name__,
                                str(e),
                                delay,
                            )
                        sleep(delay)
                    else:
                        raise
        except requests.HTTPError as e:
            if e.response is not None:
                raise PrettyHTTPError(e.response)
            else:
                raise
        if raw:
            return r
        elif r.status_code == 204 or r.text.strip() == "":
            return None
        else:
            return r.json()

    def get(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: bool = False,
    ) -> Any:
        return self.request("GET", path, params=params, headers=headers, raw=raw)

    def post(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        json: Any = None,
        data: bytes | None = None,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "POST", path, params=params, headers=headers, json=json, data=data, raw=raw
        )

    def put(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        json: Any = None,
        data: bytes | None = None,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "PUT", path, params=params, headers=headers, json=json, data=data, raw=raw
        )

    def patch(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        json: Any = None,
        data: bytes | None = None,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "PATCH", path, params=params, headers=headers, json=json, data=data, raw=raw
        )

    def delete(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        json: Any = None,
        data: bytes | None = None,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "DELETE",
            path,
            params=params,
            headers=headers,
            json=json,
            data=data,
            raw=raw,
        )

    def paginate(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
    ) -> Iterator[dict]:
        while path is not None:
            r = self.get(path, params=params, headers=headers, raw=True)
            data = r.json()
            if isinstance(data, list):
                yield from data
            else:
                assert isinstance(data, dict)
                itemses = [v for k, v in data.items() if k != "total_count"]
                if len(itemses) != 1:
                    raise ValueError(
                        f"Unique non-count key not found in {path} response"
                    )
                yield from itemses[0]
            path = r.links.get("next", {}).get("url")
            params = None


@dataclass
class RetryConfig:
    retries: int = 5
    backoff_factor: float = 1.0
    backoff_base: float = 1.25  # urllib3 uses 2
    backoff_jitter: float = 0.0
    backoff_max: float = 120.0
    total_wait: float = 600.0  ### TODO: Rethink this default
    ### TODO: Am I sure 501 errors should be retried?
    retry_statuses: Container[int] = range(500, 600)

    def backoff(self, attempts: int) -> float:
        if attempts < 2:
            # urllib3 says "most errors are resolved immediately by a second
            # try without a delay" and thus doesn't sleep on the first retry,
            # but that seems irresponsible
            return 0.1
        b = self.backoff_factor * self.backoff_base ** (attempts - 1)
        if self.backoff_jitter > 0:
            b *= random() * self.backoff_jitter
        return max(0, min(b, self.backoff_max))


@dataclass
class Retrier:
    config: RetryConfig
    attempts: int = field(init=False, default=0)
    stop_time: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.stop_time = nowdt() + timedelta(seconds=self.config.total_wait)

    def __call__(self, response: requests.Response | None) -> float | None:
        self.attempts += 1
        if self.attempts > self.config.retries:
            log.debug("Retries exhausted")
            return None
        now = nowdt()
        if now >= self.stop_time:
            log.debug("Maximum total retry wait time exceeded")
            return None
        backoff = self.config.backoff(self.attempts)
        if response is None:
            # Connection/read/etc. error
            delay = backoff
        elif response.status_code == 403:
            if "Retry-After" in response.headers:
                try:
                    delay = int(response.headers["Retry-After"]) + 1
                    log.debug("Server responded with 403 and Retry-After header")
                except (LookupError, ValueError):
                    delay = 0
            elif "rate limit" in response.text:
                if response.headers["x-ratelimit-remaining"] == "0":
                    try:
                        reset = int(response.headers["x-ratelimit-remaining"])
                        log.debug("Primary rate limit exceeded; waiting for reset")
                    except (LookupError, ValueError):
                        delay = 0
                    else:
                        delay = time() - reset + 1
                else:
                    log.debug("Secondary rate limit triggered")
                    delay = backoff
            elif response.status_code in self.config.retry_statuses:
                delay = backoff
            else:
                return None
            delay = max(delay, backoff)
        elif response.status_code in self.config.retry_statuses:
            delay = backoff
        else:
            return None
        time_left = (self.stop_time - now).total_seconds()
        return max(min(time_left, delay), 0)


@dataclass
class PrettyHTTPError(Exception):
    response: requests.Response

    def __str__(self) -> str:
        if 400 <= self.response.status_code < 500:
            msg = "{0.status_code} Client Error: {0.reason} for URL: {0.url}\n"
        elif 500 <= self.response.status_code < 600:
            msg = "{0.status_code} Server Error: {0.reason} for URL: {0.url}\n"
        else:
            msg = "{0.status_code} Unknown Error: {0.reason} for URL: {0.url}\n"
        msg = msg.format(self.response)
        try:
            resp = self.response.json()
        except ValueError:
            msg += self.response.text
        else:
            msg += json.dumps(resp, indent=4)
        return msg


def make_user_agent(name: str, version: str, url: str | None) -> str:
    s = f"{name}/{version}"
    if url is not None:
        s += f" ({url})"
    s += "requests/{} {}/{}".format(
        requests.__version__,
        platform.python_implementation(),
        platform.python_version(),
    )
    return s


def get_github_api_url() -> str:
    return os.environ.get("GITHUB_API_URL") or DEFAULT_API_URL


def nowdt() -> datetime:
    return datetime.now(timezone.utc)
