"""AutoResearch CLI - Main entry point."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()

AUTORESEARCH_DIR = Path(".autoresearch")
SETTINGS_FILE = AUTORESEARCH_DIR / "settings.json"
IDEAS_FILE = AUTORESEARCH_DIR / "ideas.json"
RESULTS_FILE = AUTORESEARCH_DIR / "results.tsv"
PROGRAM_FILE = AUTORESEARCH_DIR / "program.md"

app = typer.Typer(help="AutoResearch CLI - Manage LLM-driven research experiments")


def get_settings() -> dict:
    if not SETTINGS_FILE.exists():
        raise typer.ClickException("Not initialized. Run `autoresearch init` first.")
    return json.loads(SETTINGS_FILE.read_text())


def get_ideas() -> list[dict]:
    if not IDEAS_FILE.exists():
        return []
    return json.loads(IDEAS_FILE.read_text())


def save_ideas(ideas: list[dict]) -> None:
    IDEAS_FILE.write_text(json.dumps(ideas, indent=2))


def load_results() -> list[dict]:
    if not RESULTS_FILE.exists():
        return []
    results = []
    content = RESULTS_FILE.read_text()
    if not content.strip():
        return []
    lines = content.strip().split("\n")
    if len(lines) <= 1:
        return []
    headers = lines[0].split("\t")
    for line in lines[1:]:
        values = line.split("\t")
        if len(values) >= len(headers):
            result = dict(zip(headers, values))
            results.append(result)
    return results


def save_result(
    commit: str,
    value: float,
    memory_gb: float,
    time_minutes: float,
    description: str,
    status: str,
    run_type: str = "quick",
    verified: bool = False,
) -> None:
    line = f"{commit}\t{value}\t{memory_gb}\t{time_minutes}\t{status}\t{description}\t{run_type}\t{verified}\n"
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text(
            "commit\tloss\tmemory_gb\ttime_minutes\tstatus\tdescription\trun_type\tverified\n"
        )
    RESULTS_FILE.write_text(RESULTS_FILE.read_text() + line)


def get_editable_files() -> set[str]:
    if not PROGRAM_FILE.exists():
        return set()
    content = PROGRAM_FILE.read_text()
    editable = set()
    in_editable = False
    for line in content.split("\n"):
        line = line.strip()
        if line.upper().startswith("EDITABLE:"):
            in_editable = True
            files = line.split(":", 1)[1].strip()
            if files:
                for f in files.split(","):
                    editable.add(f.strip())
        elif line.startswith("#") or not line:
            continue
        else:
            in_editable = False
    return editable


def verify_only_editable_changed() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )
        if result.returncode != 0:
            return True, ""

        changed_files = [
            f.strip() for f in result.stdout.strip().split("\n") if f.strip()
        ]
        if not changed_files:
            return True, ""

        editable = get_editable_files()
        if not editable:
            return True, ""

        forbidden = [
            f
            for f in changed_files
            if f not in editable and not f.startswith(".autoresearch/")
        ]

        if forbidden:
            return (
                False,
                f"Changed non-editable files: {', '.join(forbidden)}. Only {editable} are editable.",
            )
        return True, ""
    except Exception:
        return True, ""


def get_current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"
    except Exception:
        return "unknown"


@app.command()
def init(
    metric: str = typer.Option(
        ..., prompt="Metric name (e.g., loss, val_bpb)", help="Metric to track"
    ),
    direction: str = typer.Option(
        ..., prompt="Direction (lower/higher)", help="Which is better"
    ),
    baseline: str = typer.Option(
        "?", prompt="Baseline value (or ? if unknown)", help="Initial baseline"
    ),
    quick_duration: int = typer.Option(
        5, prompt="Quick experiment duration (minutes)", help="Quick run duration"
    ),
    deep_duration: int = typer.Option(
        30, prompt="Deep experiment duration (minutes)", help="Deep run duration"
    ),
    quick_run: str = typer.Option(
        ...,
        prompt="Quick run command (e.g., just pretrain --time-budget 5)",
        help="Command for quick run",
    ),
    deep_run: str = typer.Option(
        ...,
        prompt="Deep run command (e.g., just pretrain --time-budget 30)",
        help="Command for deep run",
    ),
    editable_files: str = typer.Option(
        ..., prompt="Editable files (comma-separated)", help="Files agent can modify"
    ),
):
    """Initialize autoresearch in current directory."""
    if AUTORESEARCH_DIR.exists():
        raise typer.ClickException(f"{AUTORESEARCH_DIR} already exists.")

    AUTORESEARCH_DIR.mkdir()

    baseline_value = None if baseline == "?" else float(baseline)
    settings = {
        "metric": metric,
        "direction": direction,
        "baseline": baseline_value,
        "baseline_raw": baseline,
        "quick_duration": quick_duration,
        "deep_duration": deep_duration,
        "quick_run": quick_run,
        "deep_run": deep_run,
    }
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))

    IDEAS_FILE.write_text("[]")

    RESULTS_FILE.write_text(
        "commit\tloss\tmemory_gb\ttime_minutes\tstatus\tdescription\trun_type\tverified\n"
    )

    editable_list = [f.strip() for f in editable_files.split(",") if f.strip()]
    program_content = f"""# AutoResearch Program

EDITABLE: {", ".join(editable_list)}

# Run Commands
quick_run: {quick_run}
deep_run: {deep_run}

# Research Directions
- Experiment with optimizer changes
- Try different learning rate schedules
- Modify model architecture
- Adjust hyperparameters
"""
    PROGRAM_FILE.write_text(program_content)

    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if ".autoresearch/" not in content:
            gitignore_path.write_text(content + "\n.autoresearch/\n")
    else:
        gitignore_path.write_text(".autoresearch/\n")

    console.print(f"[green]Initialized[/green] {AUTORESEARCH_DIR}/")
    console.print(
        f"  - settings.json (metric: {metric}, direction: {direction}, baseline: {baseline})"
    )
    console.print(f"  - ideas.json")
    console.print(f"  - results.tsv")
    console.print(f"  - program.md")
    console.print(f"  - Added .autoresearch/ to .gitignore")


idea_app = typer.Typer(help="Manage ideas")
app.add_typer(idea_app, name="idea")


@idea_app.command("add")
def idea_add(
    text: str, output_json: bool = typer.Option(False, "--json", help="JSON output")
):
    """Add an idea to the queue."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized. Run `autoresearch init` first.")

    ideas = get_ideas()
    idea_id = max([i.get("id", 0) for i in ideas], default=0) + 1

    idea = {
        "id": idea_id,
        "text": text,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    ideas.append(idea)
    save_ideas(ideas)

    if output_json:
        print(json.dumps({"id": idea_id, "text": text}))
    else:
        console.print(f"[green]Added idea #{idea_id}:[/green] {text}")


@idea_app.command("pop")
def idea_pop(output_json: bool = typer.Option(False, "--json", help="JSON output")):
    """Get the next idea from the queue."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized. Run `autoresearch init` first.")

    settings = get_settings()
    baseline = settings.get("baseline")
    direction = settings.get("direction", "lower")

    ideas = get_ideas()
    pending = [i for i in ideas if i.get("status") == "pending"]

    if not pending:
        msg = "No ideas left. Run `autoresearch log` to review and add new ideas with `autoresearch idea add`."
        if output_json:
            print(json.dumps({"error": msg}))
        else:
            console.print(f"[yellow]{msg}[/yellow]")
        raise typer.Exit(1)

    idea = pending[0]
    idea["status"] = "in_progress"
    idea["started_at"] = datetime.now().isoformat()
    save_ideas(ideas)

    if output_json:
        print(
            json.dumps(
                {
                    "id": idea["id"],
                    "text": idea["text"],
                    "baseline": baseline,
                    "direction": direction,
                }
            )
        )
    else:
        console.print(f"[cyan]Idea #{idea['id']}:[/cyan] {idea['text']}")
        console.print(f"[dim]Baseline ({direction}-better): {baseline}[/dim]")


@idea_app.command("list")
def idea_list(output_json: bool = typer.Option(False, "--json", help="JSON output")):
    """List all ideas."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized.")

    ideas = get_ideas()
    if not ideas:
        if output_json:
            print(json.dumps([]))
        else:
            console.print("[yellow]No ideas yet[/yellow]")
        return

    pending = [i for i in ideas if i.get("status") == "pending"]

    if output_json:
        print(json.dumps(ideas, indent=2))
    else:
        table = Table(title="Ideas")
        table.add_column("ID", style="cyan")
        table.add_column("Text")
        table.add_column("Status")
        for idea in ideas:
            table.add_row(str(idea["id"]), idea["text"], idea.get("status", "pending"))
        console.print(table)
        console.print(f"\n[yellow]{len(pending)} pending[/yellow]")


def process_result(
    value: float,
    memory_gb: float,
    time_minutes: float,
    description: str,
    run_type: str = "quick",
    output_json: bool = False,
):
    """Process result and return response."""
    settings = get_settings()
    direction = settings.get("direction", "lower")
    baseline = settings.get("baseline")
    metric = settings.get("metric", "loss")

    is_better = (value < baseline) if direction == "lower" else (value > baseline)
    commit = get_current_commit()

    ideas = get_ideas()
    in_progress_ideas = [i for i in ideas if i.get("status") == "in_progress"]
    success_quick_ideas = [i for i in ideas if i.get("status") == "success_quick"]
    current_idea = None

    if run_type == "deep":
        current_idea = success_quick_ideas[0] if success_quick_ideas else None
    else:
        current_idea = in_progress_ideas[0] if in_progress_ideas else None

    if is_better:
        verified = run_type == "deep"
        status = "keep"
        save_result(
            commit,
            value,
            memory_gb,
            time_minutes,
            description,
            status,
            run_type,
            verified,
        )

        if current_idea:
            if run_type == "deep":
                current_idea["status"] = "completed"
            else:
                current_idea["status"] = "success_quick"
            save_ideas(ideas)

        if run_type == "quick":
            msg = f"SUCCESS (quick, {value} {('<' if direction == 'lower' else '>')} {baseline}). Run deep to verify with `autoresearch result-deep {value} <memory_gb> <time_minutes> <description>` or reject if insignificant with `autoresearch reject`"
        else:
            settings["baseline"] = value
            SETTINGS_FILE.write_text(json.dumps(settings, indent=2))
            msg = f"VERIFIED: {value} {('<' if direction == 'lower' else '>')} {baseline} (new baseline)"
    else:
        status = "discard"
        save_result(
            commit, value, memory_gb, time_minutes, description, status, run_type, False
        )

        if current_idea:
            current_idea["status"] = "failed"
            save_ideas(ideas)

        if run_type == "deep":
            msg = f"DEEP FAILED: {value} {('>' if direction == 'lower' else '<')} {baseline}"
        else:
            msg = f"FAILURE (quick): {value} {('>' if direction == 'lower' else '<')} {baseline}"

    if output_json:
        print(
            json.dumps(
                {
                    "value": value,
                    "baseline": baseline,
                    "status": status,
                    "is_better": is_better,
                    "run_type": run_type,
                    "verified": is_better and run_type == "deep",
                }
            )
        )
    else:
        if is_better:
            console.print(f"[green]{msg}[/green]")
        else:
            console.print(f"[red]{msg}[/red]")

    return is_better, baseline


@app.command()
def result(
    value: float = typer.Argument(..., help="Metric value"),
    memory_gb: float = typer.Argument(..., help="Peak memory in GB"),
    time_minutes: float = typer.Argument(..., help="Training time in minutes"),
    description: str = typer.Argument(..., help="Description of the experiment"),
    output_json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Record quick experiment result."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized. Run `autoresearch init` first.")

    process_result(value, memory_gb, time_minutes, description, "quick", output_json)


@app.command()
def result_deep(
    value: float = typer.Argument(..., help="Metric value"),
    memory_gb: float = typer.Argument(..., help="Peak memory in GB"),
    time_minutes: float = typer.Argument(..., help="Training time in minutes"),
    description: str = typer.Argument(..., help="Description of the experiment"),
    output_json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Record deep experiment result (verification)."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized. Run `autoresearch init` first.")

    process_result(value, memory_gb, time_minutes, description, "deep", output_json)


@app.command()
def reject(output_json: bool = typer.Option(False, "--json", help="JSON output")):
    """Reject current quick success (insignificant improvement)."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized.")

    ideas = get_ideas()
    success_quick = [i for i in ideas if i.get("status") == "success_quick"]

    if success_quick:
        idea = success_quick[0]
        idea["status"] = "rejected"
        save_ideas(ideas)
        msg = "Quick experiment rejected. No baseline change."
    else:
        msg = "No successful quick experiment to reject. Run a quick experiment first."

    if output_json:
        print(json.dumps({"status": "rejected" if success_quick else "error"}))
    else:
        if success_quick:
            console.print(f"[yellow]{msg}[/yellow]")
        else:
            console.print(f"[red]{msg}[/red]")


@app.command()
def log(
    last: int = typer.Option(10, "--last", "-n", help="Number of recent results"),
    output_json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Show experiment history."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized.")

    results = load_results()
    if not results:
        if output_json:
            print(json.dumps([]))
        else:
            console.print("[yellow]No results yet[/yellow]")
        return

    recent = results[-last:] if len(results) > last else results

    if output_json:
        print(json.dumps(recent, indent=2))
    else:
        table = Table(title=f"Last {len(recent)} Results")
        table.add_column("Commit", style="dim")
        table.add_column("Loss", style="cyan")
        table.add_column("Memory", style="cyan")
        table.add_column("Time", style="cyan")
        table.add_column("Description")
        table.add_column("Status")
        table.add_column("Type")
        for r in recent:
            style = "green" if r.get("status") == "keep" else "red"
            table.add_row(
                r.get("commit", ""),
                r.get("loss", ""),
                r.get("memory_gb", ""),
                r.get("time_minutes", ""),
                r.get("description", ""),
                f"[{style}]{r.get('status', '')}[/{style}]",
                r.get("run_type", ""),
            )
        console.print(table)


@app.command()
def status(output_json: bool = typer.Option(False, "--json", help="JSON output")):
    """Show current status."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized.")

    settings = get_settings()
    results = load_results()
    ideas = get_ideas()

    pending = len([i for i in ideas if i.get("status") == "pending"])
    last_result = results[-1] if results else None

    if output_json:
        print(
            json.dumps(
                {
                    "metric": settings.get("metric"),
                    "direction": settings.get("direction"),
                    "baseline": settings.get("baseline"),
                    "quick_duration": settings.get("quick_duration"),
                    "deep_duration": settings.get("deep_duration"),
                    "quick_run": settings.get("quick_run"),
                    "deep_run": settings.get("deep_run"),
                    "pending_ideas": pending,
                    "last_result": last_result,
                }
            )
        )
    else:
        console.print(
            f"[cyan]Metric:[/cyan] {settings.get('metric')} ({settings.get('direction')}-better)"
        )
        console.print(f"[cyan]Baseline:[/cyan] {settings.get('baseline')}")
        console.print(
            f"[cyan]Quick duration:[/cyan] {settings.get('quick_duration')} min"
        )
        console.print(
            f"[cyan]Deep duration:[/cyan] {settings.get('deep_duration')} min"
        )
        console.print(f"[cyan]Quick run:[/cyan] {settings.get('quick_run')}")
        console.print(f"[cyan]Deep run:[/cyan] {settings.get('deep_run')}")
        console.print(f"[cyan]Pending ideas:[/cyan] {pending}")
        if last_result:
            console.print(
                f"[cyan]Last result:[/cyan] {last_result.get('loss')} ({last_result.get('status')}, {last_result.get('run_type')})"
            )


@app.command()
def prompt():
    """Print program.md to stdout."""
    if not PROGRAM_FILE.exists():
        raise typer.ClickException(
            "program.md not found. Run `autoresearch init` first."
        )

    print(PROGRAM_FILE.read_text())


@app.command()
def verify():
    """Verify only editable files were changed."""
    if not AUTORESEARCH_DIR.exists():
        raise typer.ClickException("Not initialized.")

    is_valid, msg = verify_only_editable_changed()
    if is_valid:
        console.print("[green]All changes are in editable files[/green]")
    else:
        console.print(f"[red]Error:[/red] {msg}")


if __name__ == "__main__":
    app()
