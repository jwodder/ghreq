v0.6.0 (in development)
-----------------------
- Support Python 3.13 and 3.14

v0.5.0 (2023-12-17)
-------------------
- When a 403 response is received with a `Retry-After` or `x-ratelimit-reset`
  header that would result in the next retry attempt being after `total_wait`
  is exceeded, don't retry.

v0.4.0 (2023-12-15)
-------------------
- Migrated from setuptools to hatch
- Added a `set_headers` argument to the `Client` constructor for explicitly
  setting or not setting headers on sessions
- Added `timeout` arguments to the request methods
- Added `allow_redirects` argument to `Client.request()` and
  `Endpoint.request()`

v0.3.1 (2023-11-13)
-------------------
- Adjusted the type hints on `PrettyHTTPError` to indicate that the `response`
  attribute is always non-`None`

v0.3.0 (2023-11-10)
-------------------
- A session-wide `Accept` header can now be specified when constructing a
  `Client` without having to use a custom `Session`
- Added a `headers` argument to the `Client` constructor for setting arbitrary
  additional headers without having to use a custom `Session`
- Gave `Client` a `close()` method

v0.2.0 (2023-11-03)
-------------------
- The `version` argument to `make_user_agent()` is now optional
- The `url` argument to `make_user_agent()` is now actually optional

v0.1.1 (2023-10-21)
-------------------
- Fix the type annotation on `Client.__enter__` to support subclassing

v0.1.0 (2023-10-21)
-------------------
Initial release
