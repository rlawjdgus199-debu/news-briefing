import json

import pytest

from briefing.slack import send_slack

URL = "https://hooks.slack.com/services/T000/B000/secret"


def test_posts_json_with_text_and_unfurl_off():
    calls = []

    def post(url, body):
        calls.append((url, body))
        return 200
    send_slack("안녕 & hello", URL, post)
    assert len(calls) == 1 and calls[0][0] == URL
    assert json.loads(calls[0][1].decode("utf-8")) == {
        "text": "안녕 & hello", "unfurl_links": False, "unfurl_media": False,
    }


def test_non_200_raises_without_leaking_the_url():
    with pytest.raises(RuntimeError) as e:
        send_slack("x", URL, lambda url, body: 404)
    assert "404" in str(e.value) and "secret" not in str(e.value)


def test_transport_error_raises_without_leaking_the_url():
    def post(url, body):
        raise OSError(f"cannot reach {url}")
    with pytest.raises(RuntimeError) as e:
        send_slack("x", URL, post)
    assert "secret" not in str(e.value) and e.value.__cause__ is None
