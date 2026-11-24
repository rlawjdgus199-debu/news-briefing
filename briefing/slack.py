"""슬랙 수신 웹훅으로 글을 보낸다."""
import json
import urllib.error
import urllib.request
from collections.abc import Callable

Post = Callable[[str, bytes], int]  # (url, body) -> HTTP 상태 코드


def http_post_json(url: str, body: bytes) -> int:
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def send_slack(text: str, webhook_url: str, post: Post = http_post_json) -> None:
    """실패하면 RuntimeError. 웹훅 주소는 비밀 값이라 오류 메시지에 넣지 않는다."""
    body = json.dumps({"text": text, "unfurl_links": False, "unfurl_media": False}).encode("utf-8")
    try:
        status = post(webhook_url, body)
    except Exception as e:
        # 원래 예외에 주소가 들어 있을 수 있어 이어 붙이지 않는다.
        raise RuntimeError(f"슬랙 전송 실패: {type(e).__name__}") from None
    if status != 200:
        raise RuntimeError(f"슬랙 전송 실패: HTTP {status}")
