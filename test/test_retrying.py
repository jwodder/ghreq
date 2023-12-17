from __future__ import annotations
from datetime import timedelta
from math import isclose
from time import time
import pytest
from pytest_mock import MockerFixture
import requests
import responses
from ghreq import (
    DEFAULT_ACCEPT,
    DEFAULT_API_VERSION,
    Client,
    PrettyHTTPError,
    RetryConfig,
    nowdt,
)


@responses.activate
def test_retry_5xx(mocker: MockerFixture) -> None:
    for status in range(500, 506):
        responses.get(
            "https://github.example.com/api/flakey",
            status=status,
            match=(
                responses.matchers.query_param_matcher({}),
                responses.matchers.header_matcher(
                    {
                        "Accept": DEFAULT_ACCEPT,
                        "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                    }
                ),
            ),
        )
    responses.get(
        "https://github.example.com/api/flakey",
        json={"worth_it": False},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert client.get("/flakey") == {"worth_it": False}
    assert m.call_count == 6
    expected = [0.1, 1.25, 1.25**2, 1.25**3, 1.25**4, 1.25**5]
    delays = [ca.args[0] for ca in m.call_args_list]
    for exp, actual in zip(expected, delays):
        assert isclose(actual, exp, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retries_exhausted(mocker: MockerFixture) -> None:
    for _ in range(10):
        responses.get(
            "https://github.example.com/api/flakey",
            status=500,
            match=(
                responses.matchers.query_param_matcher({}),
                responses.matchers.header_matcher(
                    {
                        "Accept": DEFAULT_ACCEPT,
                        "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                    }
                ),
            ),
        )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        with pytest.raises(PrettyHTTPError) as exc:
            client.get("/flakey")
        assert str(exc.value) == (
            "500 Server Error: Internal Server Error for URL:"
            " https://github.example.com/api/flakey"
        )
    assert m.call_count == 10
    expected = [0.1] + [1.25**i for i in range(9)]
    delays = [ca.args[0] for ca in m.call_args_list]
    for exp, actual in zip(expected, delays):
        assert isclose(actual, exp, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_request_errors(mocker: MockerFixture) -> None:
    for _ in range(4):
        responses.get(
            "https://github.example.com/api/flakey",
            body=requests.RequestException("Internetting is hard"),
            match=(
                responses.matchers.query_param_matcher({}),
                responses.matchers.header_matcher(
                    {
                        "Accept": DEFAULT_ACCEPT,
                        "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                    }
                ),
            ),
        )
    responses.get(
        "https://github.example.com/api/flakey",
        json={"worth_it": False},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    cfg = RetryConfig(backoff_factor=3, backoff_base=2)
    with Client(api_url="https://github.example.com/api", retry_config=cfg) as client:
        assert client.get("/flakey") == {"worth_it": False}
    assert m.call_count == 4
    expected = [0.3, 6, 12, 24]
    delays = [ca.args[0] for ca in m.call_args_list]
    for exp, actual in zip(expected, delays):
        assert isclose(actual, exp, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_no_retry_request_value_error(mocker: MockerFixture) -> None:
    m = mocker.patch("time.sleep")
    with Client(api_url="scheme://github.lisp") as client:
        with pytest.raises(requests.exceptions.InvalidSchema):
            client.get("/flakey")
    m.assert_not_called()


@responses.activate
def test_403_retry_after(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        status=403,
        headers={"Retry-After": "7"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert client.get("/greet") == {"hello": "world"}
    m.assert_called_once()
    assert isclose(m.call_args.args[0], 7, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_403_bad_retry_after(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        status=403,
        headers={"Retry-After": "an hour"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert client.get("/greet") == {"hello": "world"}
    m.assert_called_once()
    assert isclose(m.call_args.args[0], 0.1, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_primary_rate_limit(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"message": "API rate limit exceeded"},
        status=403,
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time() + 10)),
        },
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert client.get("/greet") == {"hello": "world"}
    m.assert_called_once()
    assert isclose(m.call_args.args[0], 10, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_primary_rate_limit_bad_reset(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"message": "API rate limit exceeded"},
        status=403,
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "an hour",
        },
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert client.get("/greet") == {"hello": "world"}
    m.assert_called_once()
    assert isclose(m.call_args.args[0], 0.1, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_primary_rate_limit_missing_reset(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"message": "API rate limit exceeded"},
        status=403,
        headers={"x-ratelimit-remaining": "0"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert client.get("/greet") == {"hello": "world"}
    m.assert_called_once()
    assert isclose(m.call_args.args[0], 0.1, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_403_rate_limit_no_headers(mocker: MockerFixture) -> None:
    for _ in range(4):
        responses.get(
            "https://github.example.com/api/greet",
            json={"message": "You have exceeded a secondary rate limit.  Good luck."},
            status=403,
            match=(
                responses.matchers.query_param_matcher({}),
                responses.matchers.header_matcher(
                    {
                        "Accept": DEFAULT_ACCEPT,
                        "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                    }
                ),
            ),
        )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert client.get("/greet") == {"hello": "world"}
    assert m.call_count == 4
    expected = [0.1, 1.25, 1.25**2, 1.25**3]
    delays = [ca.args[0] for ca in m.call_args_list]
    for exp, actual in zip(expected, delays):
        assert isclose(actual, exp, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_no_retry_normal_403(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"message": "You're not allowed in."},
        status=403,
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        with pytest.raises(PrettyHTTPError) as exc:
            client.get("greet")
        assert str(exc.value) == (
            "403 Client Error: Forbidden for URL:"
            " https://github.example.com/api/greet\n"
            "\n"
            "{\n"
            '    "message": "You\'re not allowed in."\n'
            "}"
        )
    m.assert_not_called()


@responses.activate
def test_retry_normal_403_in_retry_statuses(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/enter",
        json={"message": "You're not allowed in."},
        status=403,
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/enter",
        json={"message": "Oh, wait, my mistake."},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    cfg = RetryConfig(retry_statuses=[403])
    with Client(api_url="https://github.example.com/api", retry_config=cfg) as client:
        assert client.get("enter") == {"message": "Oh, wait, my mistake."}
    m.assert_called_once()
    assert isclose(m.call_args.args[0], 0.1, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_intermixed_5xx_and_rate_limit(mocker: MockerFixture) -> None:
    for _ in range(2):
        responses.get(
            "https://github.example.com/api/greet",
            status=500,
            match=(
                responses.matchers.query_param_matcher({}),
                responses.matchers.header_matcher(
                    {
                        "Accept": DEFAULT_ACCEPT,
                        "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                    }
                ),
            ),
        )
    responses.get(
        "https://github.example.com/api/greet",
        json={"message": "You have exceeded a secondary rate limit.  Good luck."},
        status=403,
        headers={"Retry-After": "6"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"message": "You have exceeded a secondary rate limit.  Good luck."},
        status=403,
        headers={"Retry-After": "6"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    cfg = RetryConfig(backoff_base=2)
    with Client(api_url="https://github.example.com/api", retry_config=cfg) as client:
        assert client.get("/greet") == {"hello": "world"}
    assert m.call_count == 4
    expected = [0.1, 2, 6, 8]
    delays = [ca.args[0] for ca in m.call_args_list]
    for exp, actual in zip(expected, delays):
        assert isclose(actual, exp, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_after_exceeds_total_wait(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        body="Come back later.\n",
        status=403,
        headers={"Retry-After": "600"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        with pytest.raises(PrettyHTTPError) as exc:
            client.get("greet")
        assert str(exc.value) == (
            "403 Client Error: Forbidden for URL:"
            " https://github.example.com/api/greet\n"
            "\n"
            "Come back later.\n"
        )
    m.assert_not_called()


@responses.activate
def test_ratelimit_reset_exceeds_total_wait(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"message": "API rate limit exceeded"},
        status=403,
        headers={
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(time() + 3500)),
        },
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        with pytest.raises(PrettyHTTPError) as exc:
            client.get("greet")
        assert str(exc.value) == (
            "403 Client Error: Forbidden for URL:"
            " https://github.example.com/api/greet\n"
            "\n"
            "{\n"
            '    "message": "API rate limit exceeded"\n'
            "}"
        )
    m.assert_not_called()


@responses.activate
def test_retry_no_total_wait(mocker: MockerFixture) -> None:
    for _ in range(11):
        responses.get(
            "https://github.example.com/api/flakey",
            body="My bits are broken.",
            status=500,
            match=(
                responses.matchers.query_param_matcher({}),
                responses.matchers.header_matcher(
                    {
                        "Accept": DEFAULT_ACCEPT,
                        "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                    }
                ),
            ),
        )
    m = mocker.patch("time.sleep")
    cfg = RetryConfig(backoff_base=2, total_wait=None)
    with Client(api_url="https://github.example.com/api", retry_config=cfg) as client:
        with pytest.raises(PrettyHTTPError) as exc:
            client.get("/flakey")
        assert str(exc.value) == (
            "500 Server Error: Internal Server Error for URL:"
            " https://github.example.com/api/flakey\n"
            "\n"
            "My bits are broken."
        )
    assert m.call_count == 10
    expected = [0.1, 2, 4, 8, 16, 32, 64, 120, 120, 120]
    delays = [ca.args[0] for ca in m.call_args_list]
    for exp, actual in zip(expected, delays):
        assert isclose(actual, exp, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_retry_5xx_past_total_wait(mocker: MockerFixture) -> None:
    for i in range(1, 8):
        responses.get(
            "https://github.example.com/api/flakey",
            body=f"Failed attempt #{i}",
            status=500,
            match=(
                responses.matchers.query_param_matcher({}),
                responses.matchers.header_matcher(
                    {
                        "Accept": DEFAULT_ACCEPT,
                        "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                    }
                ),
            ),
        )

    now = nowdt()

    def advance_clock(duration: float) -> None:
        nonlocal now
        now += timedelta(seconds=duration)

    m = mocker.patch("time.sleep", side_effect=advance_clock)
    mocker.patch("ghreq.nowdt", side_effect=lambda: now)
    cfg = RetryConfig(backoff_base=2, total_wait=60)
    with Client(api_url="https://github.example.com/api", retry_config=cfg) as client:
        with pytest.raises(PrettyHTTPError) as exc:
            client.get("/flakey")
        assert str(exc.value) == (
            "500 Server Error: Internal Server Error for URL:"
            " https://github.example.com/api/flakey\n"
            "\n"
            "Failed attempt #7"
        )
    assert m.call_count == 6
    expected = [0.1, 2, 4, 8, 16, 29.9]
    delays = [ca.args[0] for ca in m.call_args_list]
    for exp, actual in zip(expected, delays):
        assert isclose(actual, exp, rel_tol=0.3, abs_tol=0.1)
