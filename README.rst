.. image:: https://www.repostatus.org/badges/latest/active.svg
    :target: https://www.repostatus.org/#active
    :alt: Project Status: Active — The project has reached a stable, usable
          state and is being actively developed.

.. image:: https://github.com/jwodder/ghreq/actions/workflows/test.yml/badge.svg
    :target: https://github.com/jwodder/ghreq/actions/workflows/test.yml
    :alt: CI Status

.. image:: https://codecov.io/gh/jwodder/ghreq/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/jwodder/ghreq

.. image:: https://img.shields.io/pypi/pyversions/ghreq.svg
    :target: https://pypi.org/project/ghreq/

.. image:: https://img.shields.io/github/license/jwodder/ghreq.svg
    :target: https://opensource.org/licenses/MIT
    :alt: MIT License

`GitHub <https://github.com/jwodder/ghreq>`_
| `PyPI <https://pypi.org/project/ghreq/>`_
| `Issues <https://github.com/jwodder/ghreq/issues>`_
| `Changelog <https://github.com/jwodder/ghreq/blob/master/CHANGELOG.md>`_

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

Installation
============
``ghreq`` requires Python 3.8 or higher.  Just use `pip <https://pip.pypa.io>`_
for Python 3 (You have pip, right?) to install it::

    python3 -m pip install ghreq


API
===

Classes
-------

.. code:: python

    class Client:
        def __init__(
            *,
            token: str | None = None,
            api_url: str = DEFAULT_API_URL,
            session: requests.Session | None = None,
            user_agent: str | None = None,
            accept: str | None = DEFAULT_ACCEPT,
            api_version: str | None = DEFAULT_API_VERSION,
            mutation_delay: float = 1.0,
            retry_config: RetryConfig | None = None,
        )

An HTTP client class for interacting with the GitHub REST API (or sufficiently
similar APIs).

Constructor arguments:

``token``
    The GitHub access token, if any, to use to authenticate to the API.

    This argument is ignored if a non-``None`` ``session`` is supplied.

``api_url``
    The base URL to which to append paths passed to the request methods

``session``
    A pre-configured ``requests.Session`` instance to use for making requests.

    If no session is supplied, ``Client`` instantiates a new session and sets
    the following request headers on it.  (These headers are not set on
    sessions passed to the constructor.)

    - ``Accept`` (if ``accept`` is non-``None``)
    - ``Authorization`` (set to ``"Bearer {token}"`` if ``token`` is
      non-``None``)
    - ``User-Agent`` (if ``user_agent`` is non-``None``)
    - ``X-GitHub-Api-Version`` (if ``api_version`` is non-``None``)
    - any additional headers included in ``headers``

``user_agent``
    A user agent string to include in the headers of requests.  If not set, the
    ``requests`` library's default user agent is used.

    This argument is ignored if a non-``None`` ``session`` is supplied.

``accept``
    Value to set the ``Accept`` header to.  Can be set to ``None`` to not set
    the header at all.

    This argument is ignored if a non-``None`` ``session`` is supplied.

``api_version``
    Value to set the ``X-GitHub-Api-Version`` header to.  Can be set to
    ``None`` to not set the header at all.

    This argument is ignored if a non-``None`` ``session`` is supplied.

``headers``
    Optional mapping of additional headers to set on the session after setting
    all other headers.

    This argument is ignored if a non-``None`` ``session`` is supplied.

``mutation_delay``
    When making a ``POST``, ``PATCH``, ``PUT``, or ``DELETE`` request, if the
    time since the last such request is fewer than ``mutation_delay`` seconds,
    then the client will sleep long enough to make up the difference before
    performing the request.

``retry_config``
    Configuration for the request retrying mechanism.  If not set, a
    ``RetryConfig`` instance with all default attributes will be used; see
    below.

``Client`` instances can be used as context managers, in which case they close
their internal ``requests.Session`` instances on exit (regardless of whether
the session was user-provided or not).

A ``Client`` instance can be "divided" by a string (e.g., ``client / "user"``)
to obtain an ``Endpoint`` instance that makes requests to the URL formed from
``api_url`` and the "divisor"; see below.

.. code:: python

    Client.request(
        method: str,
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any

Perform an HTTP request with the given method/verb.  If ``path`` begins with
``http://`` or ``https://``, it is used as-is for the URL of the request.
Otherwise, ``path`` is appended to the ``api_url`` value supplied to the
constructor, with a forward slash inserted in between if there isn't one
present already.  Thus, given a ``client`` constructed with the default
``api_url``, the following are equivalent:

.. code:: python

    client.request("GET", "user")

    client.request("GET", "/user")

    client.request("GET", "https://api.github.com/user")

If the request is successful, the body is decoded as JSON and returned; if the
body is empty (except possibly for whitespace), ``None`` is returned.  To make
the method return the actual ``requests.Response`` object instead, pass
``raw=True`` (or ``stream=True``, which implies it).

The remaining arguments have the same meaning as in ``requests``.

If the request fails, it may be retried with exponentially increasing wait
times between attempts; see the documentation of ``RetryConfig`` below.  If all
retries are exhausted without success, the exception from the final request is
raised.

If the request fails with a 4xx or 5xx response, a ``PrettyHTTPError`` is
raised.

.. code:: python

    Client.get(
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any

Perform a ``GET`` request.  See the documentation of ``request()`` for more
information.

.. code:: python

    Client.post(
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any

Perform a ``POST`` request.  See the documentation of ``request()`` for more
information.

.. code:: python

    Client.put(
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any

Perform a ``PUT`` request.  See the documentation of ``request()`` for more
information.

.. code:: python

    Client.patch(
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any

Perform a ``PATCH`` request.  See the documentation of ``request()`` for more
information.

.. code:: python

    Client.delete(
        path: str,
        json: Any = None,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        data: DataType = None,
        stream: bool = False,
        raw: bool = False,
    ) -> Any

Perform a ``DELETE`` request.  See the documentation of ``request()`` for more
information.

.. code:: python

    Client.paginate(
        path: str,
        *,
        params: ParamsType = None,
        headers: HeadersType = None,
        raw: Literal[True, False] = False,
    ) -> Iterator

Perform a series of paginated ``GET`` requests and yield the items from each
page.  The ``path`` and ``params`` arguments are only used for the initial
request; further requests follow the "next" entry in the ``Link`` header of
each response.

The bodies of the responses must be either JSON lists (in which case the list
elements are yielded) or JSON objects in which exactly one field is a list (in
which case the elements of that list are yielded); otherwise, an error occurs.

If ``raw`` is ``True``, then instead of yielding each page's items, the
returned iterator will yield each page as a ``requests.Response`` object.

.. code:: python

    Client.close() -> None

Close the client's internal ``requests.Session``.  No more request methods may
be called afterwards.

This method is called automatically on exit when using ``Client`` as a context
manager.

.. code:: python

    class Endpoint:
        client: Client
        url: str

A combination of a ``Client`` instance and a URL.  ``Endpoint`` has
``request()``, ``get()``, ``post()``, ``put()``, ``patch()``, ``delete()``, and
``paginate()`` methods that work the same way as for ``Client``, except that
``Endpoint``'s methods do not take ``path`` arguments; instead, they make
requests to the stored URL.  This is useful if you find yourself making
requests to the same URL and/or paths under the same URL over & over.

An ``Endpoint`` instance is constructed by applying the ``/`` (division)
operator to a ``Client`` or ``Endpoint`` instance on the left and a string on
the right.  If the string begins with ``http://`` or ``https://``, it is used
as-is for the URL of the resulting ``Endpoint``.  Otherwise, the string is
appended to the ``api_url`` or ``url`` attribute of the object on the left,
with a forward slash inserted in between if there isn't one present already.
Thus, given a ``client`` constructed with the default ``api_url``, the
following are equivalent:

.. code:: python

    client.get("repos/octocat/hello-world")

    (client / "repos/octocat/hello-world").get()

    (client / "repos" / "octocat" / "hello-world").get()

.. code:: python

    class RetryConfig:
        def __init__(
           retries: int = 10,
           backoff_factor: float = 1.0,
           backoff_base: float = 1.25,
           backoff_jitter: float = 0.0
           backoff_max: float = 120.0,
           total_wait: float | None = 300.0,
           retry_statuses: Container[int] = range(500, 600),
        )

A container for storing configuration for ``ghreq``'s retrying mechanism.  A
request is retried if (a) a ``response.RequestException`` is raised that is not
a ``ValueError`` (e.g., a connection or timeout error), (b) the server responds
with a 403 status code and either the ``Retry-After`` header is present or the
body contains the string ``"rate limit"``, or (c) the server responds with a
status code listed in ``retry_statuses``.

When a request is retried, the client sleeps for increasing amounts of time
between repeated requests until either a non-retriable response is obtained,
``retries`` retry attempts have been performed, or the total amount of time
elapsed since the start of the first request exceeds ``total_wait``, if set.

The first retry happens after sleeping for ``backoff_factor * 0.1`` seconds,
and subsequent retries happen after sleeping for ``backoff_factor *
backoff_base ** (retry_number - 1) + random.random() * backoff_jitter``
seconds, up to a maximum of ``backoff_max`` per retry.  If a ``Retry-After`` or
``x-ratelimit-reset`` header indicates a larger duration to sleep for, that
value is used instead.

.. code:: python

    class PrettyHTTPError(requests.HTTPError)

A subclass of ``requests.HTTPError`` raised automatically by the request
methods if a response with a 4xx or 5xx status code is received.  Unlike its
parent class, stringifying a ``PrettyHTTPError`` will produce a string that
contains the body of the response; if the body was JSON, that JSON will be
pretty-printed.


Constants
---------

.. code:: python

    DEFAULT_ACCEPT = "application/vnd.github+json"

The default value of the ``accept`` argument to the ``Client`` constructor

.. code:: python

    DEFAULT_API_URL = "https://api.github.com"

The default value of the ``api_url`` argument to the ``Client`` constructor

.. code:: python

    DEFAULT_API_VERSION = "2022-11-28"

The default value of the ``api_version`` argument to the ``Client`` constructor


Utility Functions
-----------------

.. code:: python

    make_user_agent(name: str, version: str | None = None, url: str | None = None) -> str

Create a user agent string with the given client name, optional version, and
optional URL.  The string will also include the version of the ``requests``
library used and the implemention & version of Python.

.. code:: python

    get_github_api_url() -> str

If the ``GITHUB_API_URL`` environment variable is set to a nonempty string,
that string is returned; otherwise, ``DEFAULT_API_URL`` is returned.
