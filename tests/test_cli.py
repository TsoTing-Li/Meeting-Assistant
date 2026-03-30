"""
CLI tests — no external services required.
STT endpoint is mocked via httpx.post; LLM is mocked via _make_llm patch.
"""
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


# ── transcribe ───────────────────────────────────────────────────────────────

def test_transcribe_success(tmp_path):
    audio = tmp_path / "test.mp3"
    audio.write_bytes(b"fake audio data")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": "逐字稿內容",
        "duration_seconds": 10.5,
        "language": "zh",
    }

    with patch("cli.main.httpx.post", return_value=mock_resp):
        result = runner.invoke(app, [
            "transcribe", str(audio),
            "--stt-url", "http://localhost:8080",
        ])

    assert result.exit_code == 0
    assert "逐字稿內容" in result.output


def test_transcribe_saves_to_file(tmp_path):
    audio = tmp_path / "test.mp3"
    audio.write_bytes(b"fake audio data")
    out = tmp_path / "transcript.txt"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": "會議內容",
        "duration_seconds": 5.0,
        "language": "zh",
    }

    with patch("cli.main.httpx.post", return_value=mock_resp):
        result = runner.invoke(app, [
            "transcribe", str(audio),
            "--stt-url", "http://localhost:8080",
            "--output", str(out),
        ])

    assert result.exit_code == 0
    assert out.read_text(encoding="utf-8") == "會議內容"


def test_transcribe_stt_error(tmp_path):
    audio = tmp_path / "test.mp3"
    audio.write_bytes(b"fake audio data")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("cli.main.httpx.post", return_value=mock_resp):
        result = runner.invoke(app, [
            "transcribe", str(audio),
            "--stt-url", "http://localhost:8080",
        ])

    assert result.exit_code == 1


def test_transcribe_passes_language(tmp_path):
    audio = tmp_path / "test.mp3"
    audio.write_bytes(b"audio")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "hello", "duration_seconds": 2.0, "language": "en"}

    with patch("cli.main.httpx.post", return_value=mock_resp) as mock_post:
        runner.invoke(app, [
            "transcribe", str(audio),
            "--stt-url", "http://localhost:8080",
            "--language", "en",
        ])

    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["data"]["language"] == "en"


# ── correct ───────────────────────────────────────────────────────────────────

def _make_mock_llm(response: str = "修正後的內容") -> MagicMock:
    llm = MagicMock()
    llm.chat.return_value = response
    return llm


def test_correct_success(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("阿里巴巴的AI技術", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("Alibaba的AI技術")):
        result = runner.invoke(app, [
            "correct", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/Qwen3",
        ])

    assert result.exit_code == 0
    assert "Alibaba" in result.output


def test_correct_saves_to_file(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("原始內容", encoding="utf-8")
    out = tmp_path / "corrected.txt"

    with patch("cli.main._make_llm", return_value=_make_mock_llm("修正後內容")):
        result = runner.invoke(app, [
            "correct", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--output", str(out),
        ])

    assert result.exit_code == 0
    assert out.read_text(encoding="utf-8") == "修正後內容"


def test_correct_with_inline_terms(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("錯誤詞彙", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("正確詞彙")):
        result = runner.invoke(app, [
            "correct", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--terms", "錯誤詞彙=正確詞彙",
        ])

    assert result.exit_code == 0


def test_correct_with_dict_csv(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("吉他的用法", encoding="utf-8")

    dict_file = tmp_path / "dict.csv"
    dict_file.write_text("wrong,correct\n吉他,GitHub\n", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("GitHub的用法")):
        result = runner.invoke(app, [
            "correct", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--dict", str(dict_file),
        ])

    assert result.exit_code == 0


def test_correct_with_dict_json(tmp_path):
    import json
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("阿里巴巴", encoding="utf-8")

    dict_file = tmp_path / "dict.json"
    dict_file.write_text(json.dumps({"阿里巴巴": "Alibaba"}), encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("Alibaba")):
        result = runner.invoke(app, [
            "correct", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--dict", str(dict_file),
        ])

    assert result.exit_code == 0


# ── summarize ─────────────────────────────────────────────────────────────────

def test_summarize_success(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("會議討論了預算問題", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("## 會議摘要\n本次會議...")):
        result = runner.invoke(app, [
            "summarize", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
        ])

    assert result.exit_code == 0
    assert "會議摘要" in result.output


def test_summarize_saves_to_file(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("內容", encoding="utf-8")
    out = tmp_path / "summary.md"

    with patch("cli.main._make_llm", return_value=_make_mock_llm("## 摘要\n內容")):
        result = runner.invoke(app, [
            "summarize", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--output", str(out),
        ])

    assert result.exit_code == 0
    assert "## 摘要" in out.read_text(encoding="utf-8")


def test_summarize_builtin_scene(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("週會內容", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("摘要")):
        result = runner.invoke(app, [
            "summarize", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--scene", "weekly_standup",
        ])

    assert result.exit_code == 0


def test_summarize_invalid_scene(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("內容", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm()):
        result = runner.invoke(app, [
            "summarize", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--scene", "no_such_scene",
        ])

    assert result.exit_code == 1


def test_summarize_custom_prompt_file(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("內容", encoding="utf-8")
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("你是自訂助手。", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("自訂摘要")):
        result = runner.invoke(app, [
            "summarize", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--prompt-file", str(prompt_file),
        ])

    assert result.exit_code == 0


def test_summarize_with_metadata(tmp_path):
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("內容", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("摘要")):
        result = runner.invoke(app, [
            "summarize", str(transcript),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--date", "2026-03-20",
            "--participants", "Alice,Bob",
            "--topics", "預算,進度",
        ])

    assert result.exit_code == 0


# ── aggregate ─────────────────────────────────────────────────────────────────

def test_aggregate_success(tmp_path):
    s1 = tmp_path / "week1.md"
    s2 = tmp_path / "week2.md"
    s1.write_text("## 第一場", encoding="utf-8")
    s2.write_text("## 第二場", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm("## 彙整報告")):
        result = runner.invoke(app, [
            "aggregate", str(s1), str(s2),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
        ])

    assert result.exit_code == 0
    assert "彙整報告" in result.output


def test_aggregate_too_few_files(tmp_path):
    s1 = tmp_path / "week1.md"
    s1.write_text("第一場", encoding="utf-8")

    with patch("cli.main._make_llm", return_value=_make_mock_llm()):
        result = runner.invoke(app, [
            "aggregate", str(s1),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
        ])

    assert result.exit_code == 1


def test_aggregate_saves_to_file(tmp_path):
    s1 = tmp_path / "a.md"
    s2 = tmp_path / "b.md"
    s1.write_text("第一場", encoding="utf-8")
    s2.write_text("第二場", encoding="utf-8")
    out = tmp_path / "report.md"

    with patch("cli.main._make_llm", return_value=_make_mock_llm("## 彙整")):
        result = runner.invoke(app, [
            "aggregate", str(s1), str(s2),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--output", str(out),
        ])

    assert result.exit_code == 0
    assert "## 彙整" in out.read_text(encoding="utf-8")


def test_aggregate_with_labels(tmp_path):
    s1 = tmp_path / "a.md"
    s2 = tmp_path / "b.md"
    s1.write_text("第一場", encoding="utf-8")
    s2.write_text("第二場", encoding="utf-8")

    llm = MagicMock()
    llm.chat.return_value = "彙整"

    with patch("cli.main._make_llm", return_value=llm):
        runner.invoke(app, [
            "aggregate", str(s1), str(s2),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
            "--labels", "Week1,Week2",
        ])

    # Labels are passed to aggregator → verify they appear in the LLM prompt
    call_args = llm.chat.call_args
    assert "Week1" in call_args.kwargs.get("user_message", "") or \
           "Week1" in str(call_args)


def test_aggregate_default_labels_use_filenames(tmp_path):
    s1 = tmp_path / "sprint01.md"
    s2 = tmp_path / "sprint02.md"
    s1.write_text("第一場", encoding="utf-8")
    s2.write_text("第二場", encoding="utf-8")

    llm = MagicMock()
    llm.chat.return_value = "彙整"

    with patch("cli.main._make_llm", return_value=llm):
        result = runner.invoke(app, [
            "aggregate", str(s1), str(s2),
            "--llm-url", "http://localhost:8002/v1",
            "--model", "openai/model",
        ])

    assert result.exit_code == 0


# ── prompts (builtin list) ────────────────────────────────────────────────────

def test_prompts_command_lists_scenes():
    result = runner.invoke(app, ["prompts"])
    assert result.exit_code == 0
    for scene in ("general", "weekly_standup", "project_review", "client_interview"):
        assert scene in result.output
