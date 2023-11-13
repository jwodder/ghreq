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
