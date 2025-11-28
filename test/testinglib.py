from __future__ import annotations
from collections.abc import Callable
import requests

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


def match_png(req: requests.PreparedRequest) -> tuple[bool, str]:
    if req.body != PNG:
        return (False, "Request body is not the expected PNG")
    else:
        return (True, "")


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
