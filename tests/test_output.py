from pydantic import HttpUrl

from ig_cli.output import to_json


def test_to_json_serializes_pydantic_http_url_as_string():
    payload = to_json({"profile_pic_url": HttpUrl("https://example.com/avatar.jpg")})

    assert '"profile_pic_url": "https://example.com/avatar.jpg"' in payload
