"""
Meeting Assistant CLI — file-based, no database.

All commands read/write local files and call external services via HTTP.
STT and LLM endpoints are specified by the user at runtime.
"""
import typer
import httpx
from pathlib import Path
from rich.console import Console
from rich import print as rprint

app = typer.Typer(name="meeting-assistant", help="AI Meeting Assistant CLI", add_completion=False)
console = Console()


def _make_llm(llm_url: str, model: str, api_key: str):
    from core.llm.litellm_client import LiteLLMClient
    return LiteLLMClient(model=model, api_key=api_key, api_base=llm_url)


def _write_output(content: str, output: Path | None) -> None:
    if output:
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]Saved to:[/green] {output}")
    else:
        console.print(content)


# ── transcribe ─────────────────────────────────────────────────────────────

@app.command()
def transcribe(
    audio_file: Path = typer.Argument(..., help="Audio file to transcribe", exists=True),
    stt_url: str = typer.Option(..., "--stt-url", help="STT service URL, e.g. http://localhost:8080"),
    language: str = typer.Option("zh", "--language", "-l", help="Audio language (zh / en)"),
    output: Path = typer.Option(None, "--output", "-o", help="Output transcript file (default: stdout)"),
):
    """Transcribe an audio file via STT service."""
    console.print(f"[cyan]Sending to STT service: {stt_url}[/cyan]")
    timeout = httpx.Timeout(connect=10.0, write=120.0, read=7200.0, pool=10.0)
    with console.status("[bold green]Transcribing..."):
        with open(audio_file, "rb") as f:
            resp = httpx.post(
                f"{stt_url.rstrip('/')}/transcribe",
                files={"audio": (audio_file.name, f, "audio/mpeg")},
                data={"language": language},
                timeout=timeout,
            )
    if resp.status_code != 200:
        console.print(f"[red]STT error {resp.status_code}: {resp.text}[/red]")
        raise typer.Exit(1)

    data = resp.json()
    console.print(f"[green]Done[/green] — {data['duration_seconds']:.1f}s · language: {data['language']}")
    _write_output(data["text"], output)


# ── correct ────────────────────────────────────────────────────────────────

@app.command()
def correct(
    transcript_file: Path = typer.Argument(..., help="Transcript text file to correct", exists=True),
    llm_url: str = typer.Option(..., "--llm-url", help="LLM base URL, e.g. http://localhost:8002/v1"),
    model: str = typer.Option(..., "--model", help="Model name, e.g. openai/Qwen/Qwen3-4B"),
    api_key: str = typer.Option("no-key", "--api-key", help="LLM API key (use 'no-key' for local servers)"),
    terms: str = typer.Option(None, "--terms", help="Inline corrections: '錯誤=正確,foo=bar'"),
    dict_file: Path = typer.Option(None, "--dict", "-d", help="CSV or JSON dictionary file", exists=True),
    output: Path = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
):
    """Correct a transcript using LLM + optional dictionary."""
    from core.correction.dictionary import CorrectionDictionary
    from core.correction.corrector import TranscriptCorrector

    text = transcript_file.read_text(encoding="utf-8")
    dictionary = CorrectionDictionary()

    if dict_file:
        if dict_file.suffix.lower() == ".json":
            dictionary.load_json(dict_file)
        else:
            dictionary.load_csv(dict_file)
        console.print(f"[dim]Loaded {len(dictionary)} entries from {dict_file.name}[/dim]")

    if terms:
        for pair in terms.split(","):
            if "=" in pair:
                wrong, correct_term = pair.split("=", 1)
                dictionary.add(wrong.strip(), correct_term.strip())
        console.print(f"[dim]Total dictionary entries: {len(dictionary)}[/dim]")

    llm = _make_llm(llm_url, model, api_key)
    corrector = TranscriptCorrector(llm=llm, dictionary=dictionary)

    with console.status("[bold green]Correcting..."):
        result = corrector.correct(text)

    console.print("[green]Correction complete[/green]")
    _write_output(result, output)


# ── summarize ──────────────────────────────────────────────────────────────

@app.command()
def summarize(
    transcript_file: Path = typer.Argument(..., help="Transcript file to summarize", exists=True),
    llm_url: str = typer.Option(..., "--llm-url", help="LLM base URL, e.g. http://localhost:8002/v1"),
    model: str = typer.Option(..., "--model", help="Model name, e.g. openai/Qwen/Qwen3-4B"),
    api_key: str = typer.Option("no-key", "--api-key", help="LLM API key"),
    scene: str = typer.Option("general", "--scene", "-s", help="Builtin scene: general|weekly_standup|project_review|client_interview"),
    prompt_file: Path = typer.Option(None, "--prompt-file", "-p", help="Path to custom system prompt .txt file"),
    date: str = typer.Option(None, "--date", help="Meeting date YYYY-MM-DD (default: today)"),
    participants: str = typer.Option(None, "--participants", help="Comma-separated participant names"),
    topics: str = typer.Option(None, "--topics", help="Comma-separated topics"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
):
    """Generate a meeting summary from a transcript file."""
    from datetime import date as date_type
    from core.summary.templates import get_template, MeetingContext
    from core.summary.summarizer import MeetingSummarizer

    text = transcript_file.read_text(encoding="utf-8")

    meeting_date = date if date else date_type.today().strftime("%Y-%m-%d")
    participant_list = [p.strip() for p in participants.split(",")] if participants else []
    topic_list = [t.strip() for t in topics.split(",")] if topics else []

    ctx = MeetingContext(
        date=meeting_date,
        meeting_type=scene,
        participants=participant_list,
        topics=topic_list,
    )

    try:
        template = get_template(scene)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    custom_system_prompt = None
    if prompt_file:
        if not prompt_file.exists():
            console.print(f"[red]Prompt file not found: {prompt_file}[/red]")
            raise typer.Exit(1)
        custom_system_prompt = prompt_file.read_text(encoding="utf-8").strip()
        console.print(f"[dim]Using custom prompt from: {prompt_file.name}[/dim]")

    llm = _make_llm(llm_url, model, api_key)
    summarizer = MeetingSummarizer(llm=llm)

    with console.status("[bold green]Generating summary..."):
        content = summarizer.summarize(text, template, ctx, system_prompt=custom_system_prompt)

    console.print("[green]Summary complete[/green]")
    _write_output(content, output)


# ── aggregate ──────────────────────────────────────────────────────────────

@app.command()
def aggregate(
    summary_files: list[Path] = typer.Argument(..., help="Summary markdown files to aggregate"),
    llm_url: str = typer.Option(..., "--llm-url", help="LLM base URL, e.g. http://localhost:8002/v1"),
    model: str = typer.Option(..., "--model", help="Model name, e.g. openai/Qwen/Qwen3-4B"),
    api_key: str = typer.Option("no-key", "--api-key", help="LLM API key"),
    labels: str = typer.Option(None, "--labels", help="Comma-separated labels for each summary file"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
):
    """Aggregate multiple meeting summaries into a cross-meeting report."""
    from core.aggregation.aggregator import MeetingAggregator

    if len(summary_files) < 2:
        console.print("[red]At least 2 summary files required.[/red]")
        raise typer.Exit(1)

    summaries_text = []
    for f in summary_files:
        if not f.exists():
            console.print(f"[red]File not found: {f}[/red]")
            raise typer.Exit(1)
        summaries_text.append(f.read_text(encoding="utf-8"))
        console.print(f"[dim]Loaded: {f.name}[/dim]")

    label_list = [l.strip() for l in labels.split(",")] if labels else [f.stem for f in summary_files]

    llm = _make_llm(llm_url, model, api_key)
    aggregator = MeetingAggregator(llm=llm)

    with console.status("[bold green]Aggregating..."):
        result = aggregator.aggregate(summaries_text, meeting_ids=[], meeting_labels=label_list)

    console.print("[green]Aggregation complete[/green]")
    _write_output(result.content, output)


# ── prompts ────────────────────────────────────────────────────────────────

@app.command("prompts")
def list_prompts():
    """List available built-in prompt scenes."""
    from core.summary.templates import BUILTIN_TEMPLATES
    from rich.table import Table

    table = Table(title="Built-in Scenes")
    table.add_column("Scene", style="cyan")
    table.add_column("Name")
    for scene, t in BUILTIN_TEMPLATES.items():
        table.add_row(scene, t.name)
    console.print(table)
    console.print("\n[dim]Use --scene <scene> or --prompt-file <path> in the summarize command[/dim]")


if __name__ == "__main__":
    app()
