from __future__ import annotations
import pytest
from ghreq import get_github_api_url


def test_get_github_api_url_no_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    assert get_github_api_url() == "https://api.github.com"


def test_get_github_api_url_empty_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_URL", "")
    assert get_github_api_url() == "https://api.github.com"


def test_get_github_api_url_from_envvar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_API_URL", "https://github.example.com/api")
    assert get_github_api_url() == "https://github.example.com/api"
