"""AI 호출은 이 파일 한 곳에서만 한다.

Claude Code를 명령줄로 불러(`claude -p`) 구독 계정으로 호출한다. API 요금이 따로 들지 않는다.
자동 실행 환경에서는 `claude setup-token`으로 받은 토큰을 CLAUDE_CODE_OAUTH_TOKEN 환경 변수로 준다.
호출 방식을 바꾸고 싶으면 make_ask_json만 고치면 된다. 나머지 코드는 AskJson만 안다.
"""
import json
import shutil
import subprocess
from collections.abc import Callable
from typing import Protocol

TIMEOUT_SECONDS = 600
Runner = Callable[[list[str], str], tuple[int, str, str]]  # (인자들, 표준 입력) -> (종료 코드, 출력, 오류 출력)


class AiError(Exception):
    """AI 호출이 실패했거나 쓸 수 없는 응답이 왔다."""


class AskJson(Protocol):
    def __call__(self, *, system: str, user: str, schema: dict) -> dict:
        """지시문과 입력을 주고, schema 모양의 JSON 응답을 딕셔너리로 받는다."""


def run_cli(args: list[str], stdin_text: str) -> tuple[int, str, str]:
    exe = shutil.which("claude")
    if exe is None:
        raise FileNotFoundError("claude 명령을 찾을 수 없습니다. Claude Code가 설치되어 있어야 합니다.")
    done = subprocess.run([exe, *args], input=stdin_text.encode("utf-8"), capture_output=True,
                          timeout=TIMEOUT_SECONDS)
    return done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")


def make_ask_json(model: str, run: Runner = run_cli, log: Callable[[str], None] = print) -> AskJson:
    def ask(*, system: str, user: str, schema: dict) -> dict:
        args = [
            "-p",
            "--model", model,
            "--tools", "",  # 도구 없이 글만 주고받는다
            "--output-format", "json",
            "--json-schema", json.dumps(schema, ensure_ascii=False),
            "--system-prompt", system,
        ]
        try:
            code, out, err = run(args, user)
        except Exception as e:
            raise AiError(f"AI 호출 실패: {type(e).__name__}: {e}") from e
        if code != 0:
            raise AiError(f"AI 호출 실패 (종료 코드 {code}): {(err or out).strip()[:300]}")
        try:
            result = json.loads(out)
        except ValueError as e:
            raise AiError("AI 응답을 읽을 수 없습니다 (JSON이 아님)") from e
        if result.get("is_error") or result.get("subtype") != "success":
            raise AiError(f"AI 호출 실패: {str(result.get('result') or result.get('subtype'))[:300]}")
        answer = result.get("structured_output")
        if not isinstance(answer, dict):
            raise AiError("AI 응답에 정해진 형식의 결과가 없습니다")
        usage = result.get("usage") or {}
        log(f"AI 사용량: 입력 {usage.get('input_tokens', '?')} 토큰, 출력 {usage.get('output_tokens', '?')} 토큰")
        return answer

    return ask
