from __future__ import annotations
from collections.abc import Callable
import requests
import responses
from ghreq import DEFAULT_ACCEPT, DEFAULT_API_VERSION, Client


def match_unset_headers(
    headers: list[str],
) -> Callable[[requests.PreparedRequest], tuple[bool, str]]:
    def matcher(req: requests.PreparedRequest) -> tuple[bool, str]:
        msg = []
        for h in headers:
            if h in req.headers:
                msg.append(f"Header {h!r} unexpectedly in request")
        if msg:
            return (False, "; ".join(msg))
        else:
            return (True, "")

    return matcher


@responses.activate
def test_header_args() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/octet-stream",
                    "Authorization": "Bearer hunter2",
                    "User-Agent": "Test/0.0.0",
                    "X-GitHub-Api-Version": "2525-01-01",
                    "Secret-Ingredient": "love",
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "hunter3"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "accept": "text/html",
                    "Authorization": "token hunter3",
                    "user-agent": "Python",
                    "x-github-api-version": "1970-01-01",
                    "Secret-Ingredient": "chocolate",
                }
            ),
        ),
    )
    with Client(
        token="hunter2",
        api_url="https://github.example.com/api",
        user_agent="Test/0.0.0",
        accept="application/octet-stream",
        api_version="2525-01-01",
        headers={"Secret-Ingredient": "love"},
    ) as client:
        assert client.get("/greet") == {"hello": "world"}
        assert client.get(
            "/greet",
            headers={
                "Authorization": "token hunter3",
                "user-agent": "Python",
                "x-github-api-version": "1970-01-01",
                "accept": "text/html",
                "Secret-Ingredient": "chocolate",
            },
        ) == {"hello": "hunter3"}


@responses.activate
def test_header_args_no_set_headers() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher({"Accept": "*/*"}),
            match_unset_headers(["Authorization", "X-GitHub-Api-Version"]),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "hunter3"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "accept": "text/html",
                    "Authorization": "token hunter3",
                    "user-agent": "Python",
                    "x-github-api-version": "1970-01-01",
                    "Secret-Ingredient": "chocolate",
                }
            ),
        ),
    )
    with Client(
        token="hunter2",
        api_url="https://github.example.com/api",
        user_agent="Test/0.0.0",
        accept="application/octet-stream",
        api_version="2525-01-01",
        headers={"Secret-Ingredient": "love"},
        set_headers=False,
    ) as client:
        assert client.get("/greet") == {"hello": "world"}
        assert client.get(
            "/greet",
            headers={
                "Authorization": "token hunter3",
                "user-agent": "Python",
                "x-github-api-version": "1970-01-01",
                "accept": "text/html",
                "Secret-Ingredient": "chocolate",
            },
        ) == {"hello": "hunter3"}


@responses.activate
def test_null_header_args() -> None:
    responses.get(
        "https://api.github.com/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher({"Accept": "*/*"}),
            match_unset_headers(["Authorization", "X-GitHub-Api-Version"]),
        ),
    )
    with Client(api_version=None, accept=None) as client:
        assert client.get("/greet") == {"hello": "world"}


@responses.activate
def test_overlapping_custom_headers() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/octet-stream",
                    "X-GitHub-Api-Version": "1.2.3",
                    "Secret-Ingredient": "love",
                }
            ),
        ),
    )
    with Client(
        api_url="https://github.example.com/api",
        api_version="2525-01-01",
        headers={
            "Secret-Ingredient": "love",
            "Accept": "application/octet-stream",
            "X-GitHub-Api-Version": "1.2.3",
        },
    ) as client:
        assert client.get("/greet") == {"hello": "world"}


@responses.activate
def test_custom_session() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher({"X-Custom": "yes"}),
            match_unset_headers(["Authorization", "X-GitHub-Api-Version"]),
        ),
    )
    s = requests.Session()
    s.headers["X-Custom"] = "yes"
    with Client(
        token="hunter2",
        api_url="https://github.example.com/api",
        user_agent="Test/0.0.0",
        api_version="2525-01-01",
        session=s,
    ) as client:
        assert client.get("/greet") == {"hello": "world"}


@responses.activate
def test_custom_session_set_headers() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "X-Custom": "yes",
                    "Accept": DEFAULT_ACCEPT,
                    "Authorization": "Bearer hunter2",
                    "User-Agent": "Test/0.0.0",
                    "X-GitHub-Api-Version": "2525-01-01",
                    "Y-Custom": "true",
                }
            ),
        ),
    )
    s = requests.Session()
    s.headers["X-Custom"] = "yes"
    with Client(
        token="hunter2",
        api_url="https://github.example.com/api",
        user_agent="Test/0.0.0",
        api_version="2525-01-01",
        headers={"Y-Custom": "true"},
        session=s,
        set_headers=True,
    ) as client:
        assert client.get("/greet") == {"hello": "world"}


@responses.activate
def test_custom_session_set_default_headers() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "Authorization": "Bearer hunter2",
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    s = requests.Session()
    with Client(
        token="hunter2",
        api_url="https://github.example.com/api",
        session=s,
        set_headers=True,
    ) as client:
        assert client.get("/greet") == {"hello": "world"}
