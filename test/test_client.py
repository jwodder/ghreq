from __future__ import annotations
import responses
from ghreq import GitHub


@responses.activate
def test_get() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "octocat"},
        match=(
            responses.matchers.query_param_matcher({"whom": "octocat"}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        body="You found the secret guacamole!",
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/vnd.github.raw",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "X-Tra": "guac",
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/greet",
        body=('{"hello": "world"}\n' * 10),
        match=(
            responses.matchers.query_param_matcher({"times": "10"}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/vnd.github+json",
                    "Authorization": "token forgot-this",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
            ),
            responses.matchers.request_kwargs_matcher({"stream": True}),
        ),
    )
    with GitHub(api_url="https://github.example.com/api") as client:
        assert client.get("/greet") == {"hello": "world"}
        assert client.get("/greet", params={"whom": "octocat"}) == {"hello": "octocat"}
        r = client.get(
            "/greet",
            headers={"Accept": "application/vnd.github.raw", "X-Tra": "guac"},
            raw=True,
        )
        assert r.text == "You found the secret guacamole!"
        r = client.get(
            "/greet",
            params={"times": 10},
            headers={"Authorization": "token forgot-this"},
            stream=True,
        )
        assert list(r.iter_lines()) == [b'{"hello": "world"}'] * 10


@responses.activate
def test_header_args() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/vnd.github+json",
                    "Authorization": "Bearer hunter2",
                    "User-Agent": "Test/0.0.0",
                    "X-GitHub-Api-Version": "2022-11-28",
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
                    "Accept": "application/vnd.github+json",
                    "Authorization": "token hunter3",
                    "user-agent": "Python",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
            ),
        ),
    )
    with GitHub(
        token="hunter2",
        api_url="https://github.example.com/api",
        user_agent="Test/0.0.0",
    ) as client:
        assert client.get("/greet") == {"hello": "world"}
        assert client.get(
            "/greet", headers={"Authorization": "token hunter3", "user-agent": "Python"}
        ) == {"hello": "hunter3"}
