from __future__ import annotations
import platform
import pytest
import requests
from ghreq import get_github_api_url, get_github_graphql_url, make_user_agent


def test_get_github_api_url_no_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    assert get_github_api_url() == "https://api.github.com"


def test_get_github_api_url_empty_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_URL", "")
    assert get_github_api_url() == "https://api.github.com"


def test_get_github_api_url_from_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_URL", "https://github.example.com/api")
    assert get_github_api_url() == "https://github.example.com/api"


def test_get_github_graphql_url_no_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_GRAPHQL_URL", raising=False)
    assert get_github_graphql_url() == "https://api.github.com/graphql"


def test_get_github_graphql_url_empty_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_GRAPHQL_URL", "")
    assert get_github_graphql_url() == "https://api.github.com/graphql"


def test_get_github_graphql_url_from_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_GRAPHQL_URL", "https://github.example.com/api/graphql")
    assert get_github_graphql_url() == "https://github.example.com/api/graphql"


@pytest.mark.parametrize(
    "version,url,start",
    [
        (
            "1.2.3",
            "https://my.site/myclient",
            "myclient/1.2.3 (https://my.site/myclient)",
        ),
        (None, "https://my.site/myclient", "myclient (https://my.site/myclient)"),
        ("1.2.3", None, "myclient/1.2.3"),
        (None, None, "myclient"),
    ],
)
def test_make_user_agent(version: str | None, url: str | None, start: str) -> None:
    expected = start + " requests/{} {}/{}".format(
        requests.__version__,
        platform.python_implementation(),
        platform.python_version(),
    )
    s = make_user_agent("myclient", version, url)
    assert s == expected
