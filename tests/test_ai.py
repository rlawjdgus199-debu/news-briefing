import json

import pytest

from briefing.ai import AiError, make_ask_json

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
          "additionalProperties": False}


def reply(**overrides):
    base = {"type": "result", "subtype": "success", "is_error": False, "structured_output": {"ok": True},
            "usage": {"input_tokens": 10, "output_tokens": 5}}
    return json.dumps({**base, **overrides})


def runner(returncode=0, stdout=None, stderr="", calls=None):
    def run(args, stdin_text):
        if calls is not None:
            calls.append((args, stdin_text))
        return returncode, reply() if stdout is None else stdout, stderr
    return run


def test_returns_structured_output_and_sends_prompt_on_stdin():
    calls = []
    ask = make_ask_json("claude-haiku-5-5", runner(calls=calls), log=lambda line: None)
    assert ask(system="시스템 지시", user="기사 목록", schema=SCHEMA) == {"ok": True}
    args, stdin_text = calls[0]
    assert stdin_text == "기사 목록"
    assert args[args.index("--model") + 1] == "claude-haiku-5-5"
    assert args[args.index("--tools") + 1] == ""          # 도구 없이 글만 주고받는다
    assert args[args.index("--output-format") + 1] == "json"
    assert json.loads(args[args.index("--json-schema") + 1]) == SCHEMA
    assert args[args.index("--system-prompt") + 1] == "시스템 지시"


def test_logs_token_usage():
    lines = []
    make_ask_json("m", runner(), log=lines.append)(system="s", user="u", schema=SCHEMA)
    assert any("10" in line and "5" in line for line in lines)


def test_nonzero_exit_raises_with_stderr():
    ask = make_ask_json("m", runner(returncode=1, stdout="", stderr="Invalid API key"), log=lambda line: None)
    with pytest.raises(AiError, match="Invalid API key"):
        ask(system="s", user="u", schema=SCHEMA)


def test_error_result_raises():
    ask = make_ask_json("m", runner(stdout=reply(is_error=True, subtype="error_during_execution", result="boom")),
                        log=lambda line: None)
    with pytest.raises(AiError, match="boom"):
        ask(system="s", user="u", schema=SCHEMA)


def test_missing_structured_output_raises():
    ask = make_ask_json("m", runner(stdout=reply(structured_output=None)), log=lambda line: None)
    with pytest.raises(AiError):
        ask(system="s", user="u", schema=SCHEMA)


def test_non_json_stdout_raises():
    ask = make_ask_json("m", runner(stdout="not json"), log=lambda line: None)
    with pytest.raises(AiError):
        ask(system="s", user="u", schema=SCHEMA)


def test_runner_failure_becomes_ai_error():
    def run(args, stdin_text):
        raise FileNotFoundError("claude")
    with pytest.raises(AiError):
        make_ask_json("m", run, log=lambda line: None)(system="s", user="u", schema=SCHEMA)


def test_nonzero_exit_with_json_stdout_reports_its_result_text():
    # 실제로 겪은 경우: 인증 실패 시 종료 코드 1과 함께 JSON이 나오고, 이유는 뒤쪽 result 칸에 있다.
    out = json.dumps({"duration_api_ms": 0, "usage": {"x": "y" * 400}, "is_error": True,
                      "result": "Invalid bearer token"})
    ask = make_ask_json("m", runner(returncode=1, stdout=out), log=lambda line: None)
    with pytest.raises(AiError, match="Invalid bearer token"):
        ask(system="s", user="u", schema=SCHEMA)
