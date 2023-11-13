"""
Minimal and opinionated GitHub API client

``ghreq`` is a simple wrapper around requests_ with various customizations
aimed at working with the GitHub REST API.  Notable features include:

- When making a request, you only need to specify the part of the URL after the
  API base URL.  You can even construct objects for making requests with a URL
  baked in.

- All request methods return decoded JSON by default.

- 4xx and 5xx responses are automatically raised as errors without needing to
  call ``raise_for_status()``.

- Errors raised for 4xx and 5xx responses include the body of the response in
  the error message.

- Support for iterating over paginated results

- The ``Accept`` and ``X-GitHub-Api-Version`` headers are automatically set to
  their recommended values.

- Follows `GitHub's recommendations for dealing with rate limits`__, including
  waiting between mutating requests and waiting & retrying in response to
  rate-limit errors

- Automatic retrying on 5xx errors with exponential backoff

.. _requests: https://requests.readthedocs.io

__ https://docs.github.com/en/rest/guides/best-practices-for-using-the-rest-api
   ?apiVersion=2022-11-28#dealing-with-rate-limits

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
import time  # Module import for mocking purposes
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal, overload
import requests

__version__ = "0.3.1"
__author__ = "John Thorvald Wodder II"
__author_email__ = "ghreq@varonathe.org"
__license__ = "MIT"
__url__ = "https://github.com/jwodder/ghreq"

__all__ = [
    "Client",
    "Endpoint",
    "PrettyHTTPError",
    "RetryConfig",
    "get_github_api_url",
    "make_user_agent",
]

log = logging.getLogger(__name__)

#: The default value of the ``accept`` argument to the `Client` constructor
DEFAULT_ACCEPT = "application/vnd.github+json"

#: The default value of the ``api_url`` argument to the `Client` constructor
DEFAULT_API_URL = "https://api.github.com"

#: The default value of the ``api_version`` argument to the `Client`
#: constructor
DEFAULT_API_VERSION = "2022-11-28"

MUTATING_METHODS = frozenset(["POST", "PATCH", "PUT", "DELETE"])

if TYPE_CHECKING:
    from typing import IO, List, Tuple, Union
    from typing_extensions import Self, TypeAlias

    ParamsValue: TypeAlias = Union[
        str, bytes, int, float, Iterable[Union[str, bytes, int, float]], None
    ]
    ParamsType: TypeAlias = Union[Mapping[str, ParamsValue], None]
    HeadersType: TypeAlias = Union[Mapping[str, Union[str, bytes, None]], None]
    DataType: TypeAlias = Union[
        Iterable[bytes], str, bytes, IO, List[Tuple[Any, Any]], Mapping[Any, Any], None
    ]


class Client:
    """
    An HTTP client class for interacting with the GitHub REST API (or
    sufficiently similar APIs).

    `Client` instances can be used as context managers, in which case they
    close their internal `requests.Session` instances on exit (regardless of
    whether the session was user-provided or not).

    A `Client` instance can be "divided" by a string (e.g., ``client /
    "user"``) to obtain an `Endpoint` instance that makes requests to the URL
    formed from ``api_url`` and the "divisor"; see below.
    """

    def __init__(
        self,
        *,
        token: str | None = None,
        api_url: str = DEFAULT_API_URL,
        session: requests.Session | None = None,
        user_agent: str | None = None,
        accept: str | None = DEFAULT_ACCEPT,
        api_version: str | None = DEFAULT_API_VERSION,
        headers: Mapping[str, str] | None = None,
        mutation_delay: float = 1.0,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """
        :param token:
            The GitHub access token, if any, to use to authenticate to the API.

            This argument is ignored if a non-`None` ``session`` is supplied.

        :param api_url:
            The base URL to which to append paths passed to the request methods

        :param session:
            A pre-configured `requests.Session` instance to use for making
            requests.

            If no session is supplied, `Client` instantiates a new session and
            sets the following request headers on it.  (These headers are not
            set on sessions passed to the constructor.)

            - :mailheader:`Accept` (if ``accept`` is non-`None`)
            - :mailheader:`Authorization` (set to ``"Bearer {token}"`` if
              ``token`` is non-`None`)
            - :mailheader:`User-Agent` (if ``user_agent`` is non-`None`)
            - :mailheader:`X-GitHub-Api-Version` (if ``api_version`` is
              non-`None`)
            - any additional headers included in ``headers``

        :param user_agent:
            A user agent string to include in the headers of requests.  If not
            set, the `requests` library's default user agent is used.

            This argument is ignored if a non-`None` ``session`` is supplied.

        :param accept:
            Value to set the :mailheader:`Accept` header to.  Can be set to
            `None` to not set the header at all.

            This argument is ignored if a non-`None` ``session`` is supplied.

        :param api_version:
            Value to set the :mailheader:`X-GitHub-Api-Version` header to.  Can
            be set to `None` to not set the header at all.

            This argument is ignored if a non-`None` ``session`` is supplied.

        :param headers:
            Optional mapping of additional headers to set on the session after
            setting all other headers.

            This argument is ignored if a non-`None` ``session`` is supplied.

        :param mutation_delay:
            When making a ``POST``, ``PATCH``, ``PUT``, or ``DELETE`` request,
            if the time since the last such request is fewer than
            ``mutation_delay`` seconds, then the client will sleep long enough
            to make up the difference before performing the request.

        :param retry_config:
            Configuration for the request retrying mechanism.  If not set, a
            `RetryConfig` instance with all default attributes will be used;
            q.v.
        """

        self.api_url = api_url
        if session is None:
            session = requests.Session()
            if token is not None:
                session.headers["Authorization"] = f"Bearer {token}"
            if user_agent is not None:
                session.headers["User-Agent"] = user_agent
            if api_version is not None:
                session.headers["X-GitHub-Api-Version"] = api_version
            if accept is not None:
                session.headers["Accept"] = accept
            if headers is not None:
                session.headers.update(headers)
        # No headers are set on pre-supplied sessions
        self.session = session
        # GitHub recommends waiting 1 second between non-GET requests in order
        # to avoid hitting secondary rate limits.
        self.mutation_delay = mutation_delay
        if retry_config is None:
            retry_config = RetryConfig()
        self.retry_config = retry_config
        self.last_mutation: datetime | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def __truediv__(self, path: str) -> Endpoint:
        return Endpoint(self, joinurl(self.api_url, path))

    def request(
        self,
        method: str,
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        """
        Perform an HTTP request with the given method/verb.  If ``path`` begins
        with ``http://`` or ``https://``, it is used as-is for the URL of the
        request.  Otherwise, ``path`` is appended to the ``api_url`` value
        supplied to the constructor, with a forward slash inserted in between
        if there isn't one present already.  Thus, given a ``client``
        constructed with the default ``api_url``, the following are equivalent:

        .. code:: python

            client.request("GET", "user")

            client.request("GET", "/user")

            client.request("GET", "https://api.github.com/user")

        If the request is successful, the body is decoded as JSON and returned;
        if the body is empty (except possibly for whitespace), `None` is
        returned.  To make the method return the actual `requests.Response`
        object instead, pass ``raw=True`` (or ``stream=True``, which implies
        it).

        The remaining arguments have the same meaning as in `requests`.

        If the request fails, it may be retried with exponentially increasing
        wait times between attempts; see the documentation of `RetryConfig`
        below.  If all retries are exhausted without success, the exception
        from the final request is raised.

        If the request fails with a 4xx or 5xx response, a `PrettyHTTPError` is
        raised.
        """

        method = method.upper()
        url = joinurl(self.api_url, path)
        log.debug("%s %s", method, url)
        if method in MUTATING_METHODS and self.last_mutation is not None:
            mutdelay = (
                self.mutation_delay - (nowdt() - self.last_mutation).total_seconds()
            )
            if mutdelay > 0:
                log.debug("Sleeping for %f seconds between mutating requests", mutdelay)
                time.sleep(mutdelay)
        req = self.session.prepare_request(
            requests.Request(
                method,
                url,
                params=params,
                headers=headers,
                json=json,
                data=data,
            )
        )
        send_kwargs = self.session.merge_environment_settings(
            req.url, proxies={}, stream=stream, verify=None, cert=None
        )
        retrier = Retrier(self.retry_config)
        try:
            while True:
                try:
                    if method in MUTATING_METHODS:
                        self.last_mutation = nowdt()
                    r = self.session.send(req, **send_kwargs)
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
                        time.sleep(delay)
                    else:
                        raise
        except requests.HTTPError as e:
            if e.response is not None:
                raise PrettyHTTPError(response=e.response, request=e.request)
            else:
                raise  # pragma: no cover
        if stream or raw:
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
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        """
        Perform a ``GET`` request.  See the documentation of `request()` for
        more information.
        """
        return self.request(
            "GET", path, params=params, headers=headers, stream=stream, raw=raw
        )

    def post(
        self,
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        """
        Perform a ``POST`` request.  See the documentation of `request()` for
        more information.
        """
        return self.request(
            "POST",
            path,
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    def put(
        self,
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        """
        Perform a ``PUT`` request.  See the documentation of `request()` for
        more information.
        """
        return self.request(
            "PUT",
            path,
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    def patch(
        self,
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        """
        Perform a ``PATCH`` request.  See the documentation of `request()` for
        more information.
        """
        return self.request(
            "PATCH",
            path,
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    def delete(
        self,
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        """
        Perform a ``DELETE`` request.  See the documentation of `request()` for
        more information.
        """
        return self.request(
            "DELETE",
            path,
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    @overload
    def paginate(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: Literal[False] = False,
    ) -> Iterator[dict]:
        ...

    @overload
    def paginate(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: Literal[True],
    ) -> Iterator[requests.Response]:
        ...

    def paginate(
        self,
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: Literal[True, False] = False,
    ) -> Iterator:
        """
        Perform a series of paginated ``GET`` requests and yield the items from
        each page.  The ``path`` and ``params`` arguments are only used for the
        initial request; further requests follow the "next" entry in the
        :mailheader:`Link` header of each response.

        The bodies of the responses must be either JSON lists (in which case
        the list elements are yielded) or JSON objects in which exactly one
        field is a list (in which case the elements of that list are yielded);
        otherwise, an error occurs.

        If ``raw`` is `True`, then instead of yielding each page's items, the
        returned iterator will yield each page as a `requests.Response` object.
        """
        while path is not None:
            r = self.get(path, params=params, headers=headers, raw=True)
            if raw:
                yield r
            else:
                data = r.json()
                if isinstance(data, list):
                    yield from data
                else:
                    assert isinstance(data, dict)
                    itemses = [v for v in data.values() if isinstance(v, list)]
                    if len(itemses) != 1:
                        raise ValueError(
                            f"Unique list field not found in {path} response"
                        )
                    yield from itemses[0]
            path = r.links.get("next", {}).get("url")
            params = None

    def close(self) -> None:
        """
        Close the client's internal `requests.Session`.  No more request
        methods may be called afterwards.

        This method is called automatically on exit when using `Client` as a
        context manager.
        """
        self.session.close()


@dataclass
class Endpoint:
    """
    A combination of a `Client` instance and a URL.  `Endpoint` has
    `request()`, `get()`, `post()`, `put()`, `patch()`, `delete()`, and
    `paginate()` methods that work the same way as for `Client`, except that
    `Endpoint`'s methods do not take ``path`` arguments; instead, they make
    requests to the stored URL.  This is useful if you find yourself making
    requests to the same URL and/or paths under the same URL over & over.

    An `Endpoint` instance is constructed by applying the ``/`` (division)
    operator to a `Client` or `Endpoint` instance on the left and a string on
    the right.  If the string begins with ``http://`` or ``https://``, it is
    used as-is for the URL of the resulting `Endpoint`.  Otherwise, the string
    is appended to the ``api_url`` or ``url`` attribute of the object on the
    left, with a forward slash inserted in between if there isn't one present
    already.  Thus, given a ``client`` constructed with the default
    ``api_url``, the following are equivalent:

    .. code:: python

        client.get("repos/octocat/hello-world")

        (client / "repos/octocat/hello-world").get()

        (client / "repos" / "octocat" / "hello-world").get()
    """

    client: Client
    url: str

    def __truediv__(self, path: str) -> Endpoint:
        return type(self)(self.client, joinurl(self.url, path))

    def request(
        self,
        method: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        return self.client.request(
            method,
            self.url,
            json=json,
            params=params,
            headers=headers,
            data=data,
            stream=stream,
            raw=raw,
        )

    def get(
        self,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "GET", params=params, headers=headers, stream=stream, raw=raw
        )

    def post(
        self,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "POST",
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    def put(
        self,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "PUT",
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    def patch(
        self,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "PATCH",
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    def delete(
        self,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any:
        return self.request(
            "DELETE",
            params=params,
            headers=headers,
            json=json,
            data=data,
            stream=stream,
            raw=raw,
        )

    @overload
    def paginate(
        self,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: Literal[False] = False,
    ) -> Iterator[dict]:
        ...

    @overload
    def paginate(
        self,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: Literal[True],
    ) -> Iterator[requests.Response]:
        ...

    def paginate(
        self,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: Literal[True, False] = False,
    ) -> Iterator:
        return self.client.paginate(self.url, params=params, headers=headers, raw=raw)


@dataclass
class RetryConfig:
    """
    A container for storing configuration for `ghreq`'s retrying mechanism.  A
    request is retried if (a) a `response.RequestException` is raised that is
    not a `ValueError` (e.g., a connection or timeout error), (b) the server
    responds with a 403 status code and either the :mailheader:`Retry-After`
    header is present or the body contains the string ``"rate limit"``, or (c)
    the server responds with a status code listed in ``retry_statuses``.

    When a request is retried, the client sleeps for increasing amounts of time
    between repeated requests until either a non-retriable response is
    obtained, ``retries`` retry attempts have been performed, or the total
    amount of time elapsed since the start of the first request exceeds
    ``total_wait``, if set.

    The first retry happens after sleeping for ``backoff_factor * 0.1``
    seconds, and subsequent retries happen after sleeping for ``backoff_factor
    * backoff_base ** (retry_number - 1) + random.random() * backoff_jitter``
    seconds, up to a maximum of ``backoff_max`` per retry.  If a
    :mailheader:`Retry-After` or :mailheader:`x-ratelimit-reset` header
    indicates a larger duration to sleep for, that value is used instead.
    """

    retries: int = 10
    backoff_factor: float = 1.0
    backoff_base: float = 1.25  # urllib3 uses 2
    backoff_jitter: float = 0.0
    backoff_max: float = 120.0
    total_wait: float | None = 300.0  ### TODO: Rethink this default
    ### TODO: Am I sure 501 errors should be retried?
    retry_statuses: Container[int] = range(500, 600)

    def backoff(self, attempts: int) -> float:
        if attempts < 2:
            # urllib3 says "most errors are resolved immediately by a second
            # try without a delay" and thus doesn't sleep on the first retry,
            # but that seems irresponsible
            return self.backoff_factor * 0.1
        b = self.backoff_factor * self.backoff_base ** (attempts - 1)
        if self.backoff_jitter > 0:
            b += random() * self.backoff_jitter
        return max(0, min(b, self.backoff_max))


@dataclass
class Retrier:
    config: RetryConfig
    attempts: int = field(init=False, default=0)
    stop_time: datetime | None = field(init=False)

    def __post_init__(self) -> None:
        if self.config.total_wait is not None:
            self.stop_time = nowdt() + timedelta(seconds=self.config.total_wait)
        else:
            self.stop_time = None

    def __call__(self, response: requests.Response | None) -> float | None:
        self.attempts += 1
        if self.attempts > self.config.retries:
            log.debug("Retries exhausted")
            return None
        now = nowdt()
        if self.stop_time is not None and now >= self.stop_time:
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
                except ValueError:
                    delay = 0
            elif "rate limit" in response.text:
                if response.headers.get("x-ratelimit-remaining") == "0":
                    try:
                        reset = int(response.headers["x-ratelimit-reset"])
                        log.debug("Primary rate limit exceeded; waiting for reset")
                    except (LookupError, ValueError):
                        delay = 0
                    else:
                        delay = reset - time.time() + 1
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
        if self.stop_time is not None:
            time_left = (self.stop_time - now).total_seconds()
            delay = min(time_left, delay)
        return max(delay, 0)


class PrettyHTTPError(requests.HTTPError):
    """
    A subclass of `requests.HTTPError` raised automatically by the request
    methods if a response with a 4xx or 5xx status code is received.  Unlike
    its parent class, stringifying a `PrettyHTTPError` will produce a string
    that contains the body of the response; if the body was JSON, that JSON
    will be pretty-printed.
    """

    response: requests.Response

    def __str__(self) -> str:
        if 400 <= self.response.status_code < 500:
            msg = "{0.status_code} Client Error: {0.reason} for URL: {0.url}"
        elif 500 <= self.response.status_code < 600:
            msg = "{0.status_code} Server Error: {0.reason} for URL: {0.url}"
        else:
            msg = (  # pragma: no cover
                "{0.status_code} Unknown Error: {0.reason} for URL: {0.url}"
            )
        msg = msg.format(self.response)
        if self.response.text.strip():
            try:
                resp = self.response.json()
            except ValueError:
                msg += "\n\n" + self.response.text
            else:
                msg += "\n\n" + json.dumps(resp, indent=4)
        return msg


def make_user_agent(
    name: str, version: str | None = None, url: str | None = None
) -> str:
    """
    Create a user agent string with the given client name, optional version,
    and optional URL.  The string will also include the version of the
    `requests` library used and the implemention & version of Python.
    """
    s = name
    if version is not None:
        s += f"/{version}"
    if url is not None:
        s += f" ({url})"
    s += " requests/{} {}/{}".format(
        requests.__version__,
        platform.python_implementation(),
        platform.python_version(),
    )
    return s


def get_github_api_url() -> str:
    """
    If the :envvar:`GITHUB_API_URL` environment variable is set to a nonempty
    string, that string is returned; otherwise, `DEFAULT_API_URL` is returned.
    """
    return os.environ.get("GITHUB_API_URL") or DEFAULT_API_URL


def nowdt() -> datetime:
    return datetime.now(timezone.utc)


def joinurl(base: str, path: str) -> str:
    if path.lower().startswith(("http://", "https://")):
        return path
    else:
        return base.rstrip("/") + "/" + path.lstrip("/")
