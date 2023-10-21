from __future__ import annotations
from math import isclose
from pytest_mock import MockerFixture
import requests
import responses
from ghreq import DEFAULT_ACCEPT, DEFAULT_API_VERSION, Client

PNG = bytes.fromhex(
    "89 50 4e 47 0d 0a 1a 0a  00 00 00 0d 49 48 44 52"
    "00 00 00 10 00 00 00 10  08 06 00 00 00 1f f3 ff"
    "61 00 00 00 06 62 4b 47  44 00 ff 00 ff 00 ff a0"
    "bd a7 93 00 00 00 09 70  48 59 73 00 00 00 48 00"
    "00 00 48 00 46 c9 6b 3e  00 00 00 09 76 70 41 67"
    "00 00 00 10 00 00 00 10  00 5c c6 ad c3 00 00 00"
    "5b 49 44 41 54 38 cb c5  92 51 0a c0 30 08 43 7d"
    "b2 fb 5f 39 fb 12 da 61  a9 c3 8e f9 a7 98 98 48"
    "90 64 9d f2 16 da cc ae  b1 01 26 39 92 d8 11 10"
    "16 9e e0 8c 64 dc 89 b9  67 80 ca e5 f3 3f a8 5c"
    "cd 76 52 05 e1 b5 42 ea  1d f0 91 1f b4 09 78 13"
    "e5 52 0e 00 ad 42 f5 bf  85 4f 14 dc 46 b3 32 11"
    "6c b1 43 99 00 00 00 00  49 45 4e 44 ae 42 60 82"
)


@responses.activate
def test_get(mocker: MockerFixture) -> None:
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
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "octocat"},
        match=(
            responses.matchers.query_param_matcher({"whom": "octocat"}),
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
        body="You found the secret guacamole!",
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": "application/vnd.github.raw",
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
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
                    "Accept": DEFAULT_ACCEPT,
                    "Authorization": "token forgot-this",
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
            responses.matchers.request_kwargs_matcher({"stream": True}),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert (client / "greet").get() == {"hello": "world"}
        assert (client / "greet").get(params={"whom": "octocat"}) == {
            "hello": "octocat"
        }
        r = (client / "greet").get(
            headers={"Accept": "application/vnd.github.raw", "X-Tra": "guac"},
            raw=True,
        )
        assert r.text == "You found the secret guacamole!"
        r = (client / "greet").get(
            params={"times": 10},
            headers={"Authorization": "token forgot-this"},
            stream=True,
        )
        assert list(r.iter_lines()) == [b'{"hello": "world"}'] * 10
    m.assert_not_called()


@responses.activate
def test_header_args() -> None:
    responses.get(
        "https://github.example.com/api/greet",
        json={"hello": "world"},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "Authorization": "Bearer hunter2",
                    "User-Agent": "Test/0.0.0",
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
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
                    "Accept": DEFAULT_ACCEPT,
                    "Authorization": "token hunter3",
                    "user-agent": "Python",
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    with Client(
        token="hunter2",
        api_url="https://github.example.com/api",
        user_agent="Test/0.0.0",
    ) as client:
        assert (client / "greet").get() == {"hello": "world"}
        assert (client / "greet").get(
            headers={"Authorization": "token hunter3", "user-agent": "Python"}
        ) == {"hello": "hunter3"}


@responses.activate
def test_post(mocker: MockerFixture) -> None:
    def match_png(req: requests.PreparedRequest) -> tuple[bool, str]:
        if req.body != PNG:
            return (False, "Request body is not the expected PNG")
        else:
            return (True, "")

    responses.post(
        "https://github.example.com/api/widgets",
        json={"name": "Widgey", "color": "blue", "id": 1},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
            responses.matchers.json_params_matcher({"name": "Widgey", "color": "blue"}),
        ),
    )
    responses.post(
        "https://github.example.com/api/widgets/1/photo",
        json={"good_photo": True},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "Content-Type": "image/png",
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
            match_png,
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert (client / "widgets").post({"name": "Widgey", "color": "blue"}) == {
            "name": "Widgey",
            "color": "blue",
            "id": 1,
        }
        assert (client / "widgets" / "1" / "photo").post(
            data=PNG, headers={"Content-Type": "image/png"}
        ) == {"good_photo": True}
    m.assert_called_once()
    assert isclose(m.call_args.args[0], 1.0, rel_tol=0.3, abs_tol=0.1)


@responses.activate
def test_put(mocker: MockerFixture) -> None:
    responses.put(
        "https://github.example.com/api/widgets/1/flavors",
        json={
            "name": "Widgey",
            "color": "blue",
            "id": 1,
            "flavors": ["spicy", "sweet"],
        },
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
            responses.matchers.json_params_matcher(["spicy", "sweet"]),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert (client / "widgets" / "1" / "flavors").put(["spicy", "sweet"]) == {
            "name": "Widgey",
            "color": "blue",
            "id": 1,
            "flavors": ["spicy", "sweet"],
        }
    m.assert_not_called()


@responses.activate
def test_patch(mocker: MockerFixture) -> None:
    responses.patch(
        "https://github.example.com/api/widgets/1",
        json={"name": "Widgey", "color": "red", "id": 1},
        match=(
            responses.matchers.query_param_matcher({}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
            responses.matchers.json_params_matcher({"color": "red"}),
        ),
    )
    m = mocker.patch("time.sleep")
    with Client(api_url="https://github.example.com/api") as client:
        assert (client / "widgets" / "1").patch({"color": "red"}) == {
            "name": "Widgey",
            "color": "red",
            "id": 1,
        }
    m.assert_not_called()


@responses.activate
def test_delete(mocker: MockerFixture) -> None:
    responses.delete(
        "https://github.example.com/api/widgets/1",
        status=204,
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
        assert (client / "widgets" / "1").delete() is None
    m.assert_not_called()


@responses.activate
def test_paginate_list(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/widgets",
        json=[
            {"name": "Widgey", "color": "blue", "id": 1},
            {"name": "Pidgey", "color": "tawny", "id": 2},
            {"name": "Fidgety", "color": "purple", "id": 3},
            {"name": "Refridgey", "color": "green", "id": 4},
            {"name": "Clyde", "color": "orange", "id": 5},
        ],
        headers={"Link": '<https://github.example.com/api/widgets?page=2>; rel="next"'},
        match=(
            responses.matchers.query_param_matcher({"superfluous": "yes"}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/widgets",
        json=[
            {"name": "Sprocket", "color": "yellow", "id": 6},
            {"name": "Sprinkle", "color": "pink", "id": 7},
            {"name": "Spigot", "color": "puce", "id": 8},
            {"name": "Spengler", "color": "red", "id": 9},
            {"name": "Sue", "color": "orange", "id": 10},
        ],
        headers={"Link": '<https://github.example.com/api/widgets?page=3>; rel="next"'},
        match=(
            responses.matchers.query_param_matcher({"page": "2"}),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/widgets",
        json=[
            {"name": "Nut", "color": "green", "id": 11},
            {"name": "Bolt", "color": "grey", "id": 12},
        ],
        match=(
            responses.matchers.query_param_matcher({"page": "3"}),
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
        assert list((client / "widgets").paginate(params={"superfluous": "yes"})) == [
            {"name": "Widgey", "color": "blue", "id": 1},
            {"name": "Pidgey", "color": "tawny", "id": 2},
            {"name": "Fidgety", "color": "purple", "id": 3},
            {"name": "Refridgey", "color": "green", "id": 4},
            {"name": "Clyde", "color": "orange", "id": 5},
            {"name": "Sprocket", "color": "yellow", "id": 6},
            {"name": "Sprinkle", "color": "pink", "id": 7},
            {"name": "Spigot", "color": "puce", "id": 8},
            {"name": "Spengler", "color": "red", "id": 9},
            {"name": "Sue", "color": "orange", "id": 10},
            {"name": "Nut", "color": "green", "id": 11},
            {"name": "Bolt", "color": "grey", "id": 12},
        ]
    m.assert_not_called()


@responses.activate
def test_paginate_dict(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/search/widgets",
        json={
            "total_count": 8,
            "incomplete_results": False,
            "results": [
                {"name": "Widgey", "color": "blue", "id": 1},
                {"name": "Pidgey", "color": "tawny", "id": 2},
                {"name": "Fidgety", "color": "purple", "id": 3},
                {"name": "Refridgey", "color": "green", "id": 4},
                {"name": "Sprocket", "color": "yellow", "id": 6},
            ],
        },
        headers={
            "Link": '<https://github.example.com/api/search/widgets?q=is:widgety&page=2>; rel="next"'  # noqa: B950
        },
        match=(
            responses.matchers.query_param_matcher(
                {"superfluous": "yes", "q": "is:widgety"}
            ),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/search/widgets",
        json={
            "total_count": 8,
            "incomplete_results": False,
            "results": [
                {"name": "Spigot", "color": "puce", "id": 8},
                {"name": "Nut", "color": "green", "id": 11},
                {"name": "Bolt", "color": "grey", "id": 12},
            ],
        },
        match=(
            responses.matchers.query_param_matcher({"q": "is:widgety", "page": "2"}),
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
        assert list(
            (client / "search" / "widgets").paginate(
                params={"superfluous": "yes", "q": "is:widgety"}
            )
        ) == [
            {"name": "Widgey", "color": "blue", "id": 1},
            {"name": "Pidgey", "color": "tawny", "id": 2},
            {"name": "Fidgety", "color": "purple", "id": 3},
            {"name": "Refridgey", "color": "green", "id": 4},
            {"name": "Sprocket", "color": "yellow", "id": 6},
            {"name": "Spigot", "color": "puce", "id": 8},
            {"name": "Nut", "color": "green", "id": 11},
            {"name": "Bolt", "color": "grey", "id": 12},
        ]
    m.assert_not_called()


@responses.activate
def test_paginate_raw(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.com/api/search/widgets",
        json={
            "total_count": 8,
            "incomplete_results": False,
            "results": [
                {"name": "Widgey", "color": "blue", "id": 1},
                {"name": "Pidgey", "color": "tawny", "id": 2},
                {"name": "Fidgety", "color": "purple", "id": 3},
                {"name": "Refridgey", "color": "green", "id": 4},
                {"name": "Sprocket", "color": "yellow", "id": 6},
            ],
        },
        headers={
            "Link": '<https://github.example.com/api/search/widgets?q=is:widgety&page=2>; rel="next"'  # noqa: B950
        },
        match=(
            responses.matchers.query_param_matcher(
                {"superfluous": "yes", "q": "is:widgety"}
            ),
            responses.matchers.header_matcher(
                {
                    "Accept": DEFAULT_ACCEPT,
                    "X-GitHub-Api-Version": DEFAULT_API_VERSION,
                }
            ),
        ),
    )
    responses.get(
        "https://github.example.com/api/search/widgets",
        json={
            "total_count": 8,
            "incomplete_results": False,
            "results": [
                {"name": "Spigot", "color": "puce", "id": 8},
                {"name": "Nut", "color": "green", "id": 11},
                {"name": "Bolt", "color": "grey", "id": 12},
            ],
        },
        match=(
            responses.matchers.query_param_matcher({"q": "is:widgety", "page": "2"}),
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
        pages = list(
            (client / "search/widgets").paginate(
                params={"superfluous": "yes", "q": "is:widgety"}, raw=True
            )
        )
        assert len(pages) == 2
        assert pages[0].json() == {
            "total_count": 8,
            "incomplete_results": False,
            "results": [
                {"name": "Widgey", "color": "blue", "id": 1},
                {"name": "Pidgey", "color": "tawny", "id": 2},
                {"name": "Fidgety", "color": "purple", "id": 3},
                {"name": "Refridgey", "color": "green", "id": 4},
                {"name": "Sprocket", "color": "yellow", "id": 6},
            ],
        }
        assert pages[1].json() == {
            "total_count": 8,
            "incomplete_results": False,
            "results": [
                {"name": "Spigot", "color": "puce", "id": 8},
                {"name": "Nut", "color": "green", "id": 11},
                {"name": "Bolt", "color": "grey", "id": 12},
            ],
        }
    m.assert_not_called()


@responses.activate
def test_get_full_url(mocker: MockerFixture) -> None:
    responses.get(
        "https://github.example.net/api/greet",
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
    responses.get(
        "http://github.example.org/api/greet",
        json={"hello": "octocat"},
        match=(
            responses.matchers.query_param_matcher({"whom": "octocat"}),
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
        assert (client / "https://github.example.net/api/greet").get() == {
            "hello": "world"
        }
        assert (client / "http://github.example.org/api/greet").get(
            params={"whom": "octocat"}
        ) == {"hello": "octocat"}
    m.assert_not_called()


@responses.activate
def test_slashed_path(mocker: MockerFixture) -> None:
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
    responses.get(
        "https://github.example.com/api/greet/",
        json={"hello": "world/"},
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
        "https://github.example.com/api/widgets/test%20widget",
        json={"name": "Test widget", "color": "taupe", "id": 0},
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
        assert (client / "/greet").get() == {"hello": "world"}
        assert (client / "/greet/").get() == {"hello": "world/"}
        assert (client / "/widgets/test widget").get() == {
            "name": "Test widget",
            "color": "taupe",
            "id": 0,
        }
    m.assert_not_called()
