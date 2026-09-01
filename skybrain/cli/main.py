import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

from skybrain import __version__
from skybrain.core.config import settings
from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS
from skybrain.server.supervisor import DaemonSupervisor

app = typer.Typer(name="skybrain", help="🧠 SkyBrain: Universal On-Device AI Serving Daemon")
model_app = typer.Typer(name="model", help="Manage and download AI models")
app.add_typer(model_app)

console = Console()
catalog = ModelCatalog()


def _download_model_with_progress(key: str) -> None:
    preset = MODEL_PRESETS[key]
    console.print(f"[bold cyan]📥 Auto-Provisioning: Downloading {preset['name']} ({preset['description']})...[/bold cyan]")
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(preset["name"], total=None)

        def _update_progress(downloaded: int, total: int):
            progress.update(task, total=total, completed=downloaded)

        try:
            path = catalog.download(key=key, progress_callback=_update_progress)
            console.print(f"[bold green]🎉 Model successfully downloaded and ready:[/bold green] {path}")
        except Exception as e:
            console.print(f"[bold red]❌ Auto-download failed: {e}[/bold red]")
            raise typer.Exit(1)


@app.command()
def version():
    """Prints SkyBrain version."""
    console.print(f"[bold cyan]SkyBrain[/bold cyan] version [bold green]{__version__}[/bold green]")


@app.command()
def start(
    host: str = typer.Option(settings.host, "--host", "-h", help="Bind host address"),
    port: int = typer.Option(settings.port, "--port", "-p", help="Bind port number"),
    auto_download: bool = typer.Option(True, "--auto-download/--no-auto-download", "-d/-nd", help="Automatically download missing models before starting"),
    force: bool = typer.Option(False, "--force", "-f", help="Force terminate any stale processes and restart")
):
    """Starts the background SkyBrain OpenAI-compatible serving daemon."""
    if DaemonSupervisor.is_running() and not force:
        console.print("[bold yellow]⚡ SkyBrain daemon is already running.[/bold yellow]")
        return

    active_key = catalog.get_active_key()
    if not catalog.is_installed(active_key):
        if auto_download:
            console.print(f"[bold yellow]⚠️ Active model '{active_key}' not found locally.[/bold yellow]")
            _download_model_with_progress(active_key)
        else:
            console.print(f"[bold red]❌ Active model '{active_key}' is not downloaded yet.[/bold red]")
            console.print(f"[dim]Run 'skybrain model download {active_key}' or use '--auto-download'.[/dim]")
            raise typer.Exit(1)

    console.print(f"[bold cyan]🚀 Starting SkyBrain daemon on http://{host}:{port}...[/bold cyan]")
    success = DaemonSupervisor.start(host=host, port=port, force=force)
    if success:
        pid = DaemonSupervisor.get_pid()
        console.print(f"[bold green]✅ SkyBrain daemon running in background (PID: {pid})[/bold green]")
        console.print(f"• Endpoint: [underline]http://{host}:{port}/v1/chat/completions[/underline]")
        console.print(f"• Active Model: [bold]{catalog.get_active_key()}[/bold]")
    else:
        console.print("[bold red]❌ Failed to start SkyBrain daemon. Check ~/.skybrain/skybrain.log[/bold red]")
        raise typer.Exit(1)


@app.command()
def stop():
    """Stops the running SkyBrain daemon safely."""
    if not DaemonSupervisor.is_running():
        console.print("[bold yellow]⚡ SkyBrain daemon is not running.[/bold yellow]")
        return

    DaemonSupervisor.stop()
    console.print("[bold green]🛑 SkyBrain daemon has been stopped and cleaned up successfully.[/bold green]")


@app.command()
def restart(
    host: str = typer.Option(settings.host, "--host", "-h", help="Bind host address"),
    port: int = typer.Option(settings.port, "--port", "-p", help="Bind port number")
):
    """Safely cleans up existing processes and restarts SkyBrain daemon."""
    console.print("[bold cyan]🔄 Cleaning up and restarting SkyBrain daemon...[/bold cyan]")
    success = DaemonSupervisor.restart(host=host, port=port)
    if success:
        pid = DaemonSupervisor.get_pid()
        console.print(f"[bold green]✅ SkyBrain daemon successfully restarted (PID: {pid})[/bold green]")
    else:
        console.print("[bold red]❌ Failed to restart SkyBrain daemon. Check ~/.skybrain/skybrain.log[/bold red]")
        raise typer.Exit(1)


@app.command()
def status():
    """Displays daemon health, active model, and port status."""
    pid = DaemonSupervisor.get_pid()
    health = DaemonSupervisor.check_health()
    active_key = catalog.get_active_key()
    active_path = catalog.get_model_path(active_key)
    size_mb = round(active_path.stat().st_size / (1024 * 1024), 2) if active_path.exists() else 0.0

    table = Table(title="🧠 SkyBrain Daemon Status", header_style="bold cyan")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("Service Status", "[bold green]🟢 Active (Running)[/bold green]" if pid else "[bold red]🔴 Inactive (Stopped)[/bold red]")
    table.add_row("Process PID", str(pid) if pid else "-")
    table.add_row("REST API Endpoint", f"http://{settings.host}:{settings.port}/v1" if pid else "-")
    table.add_row("Active Model Key", active_key)
    table.add_row("Active Model Name", MODEL_PRESETS.get(active_key, {}).get("name", "Unknown"))
    table.add_row("Storage Path", str(active_path))
    table.add_row("Model Size", f"{size_mb} MB")
    table.add_row("API Health", "[green]Healthy[/green]" if health else "[dim]Unreachable[/dim]")

    console.print(table)


@model_app.command(name="list")
def model_list():
    """Lists all available AI model presets and their status."""
    presets = catalog.list_models()
    table = Table(title="🤖 SkyBrain AI Model Catalog", header_style="bold magenta")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Model Name", style="bold")
    table.add_column("Context", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Status", style="bold")
    table.add_column("Active", justify="center")

    for p in presets:
        status = "[green]Installed[/green]" if p["installed"] else "[dim]Not downloaded[/dim]"
        size_str = f"{p['size_mb']} MB" if p["installed"] else "-"
        active_str = "🟢 [bold green]YES[/bold green]" if p["active"] else "-"
        ctx_str = f"{p['context_length'] // 1024}k tokens"
        table.add_row(p["key"], p["name"], ctx_str, size_str, status, active_str)

    console.print(table)
    console.print("\n[dim]Commands: 'skybrain model download [key]' | 'skybrain model use [key]'[/dim]")


@model_app.command(name="use")
def model_use(
    key: str = typer.Argument(..., help="Model preset key to activate"),
    auto_download: bool = typer.Option(True, "--auto-download/--no-auto-download", "-d/-nd", help="Automatically download model if missing")
):
    """Switches the active AI model."""
    clean_key = key.strip().lower()
    if clean_key not in MODEL_PRESETS:
        console.print(f"[bold red]❌ Unknown preset:[/bold red] '{clean_key}'. Available: {list(MODEL_PRESETS.keys())}")
        raise typer.Exit(1)

    catalog.set_active_key(clean_key)
    p = MODEL_PRESETS[clean_key]
    
    if not catalog.is_installed(clean_key):
        if auto_download:
            console.print(f"[bold yellow]⚠️ Model '{p['name']}' is not installed locally. Auto-downloading...[/bold yellow]")
            _download_model_with_progress(clean_key)
        else:
            console.print(f"[bold yellow]⚠️ Model switched to '{p['name']}', but weights are not downloaded yet.[/bold yellow]")
            console.print(f"[dim]Run 'skybrain model download {clean_key}' before starting the daemon.[/dim]")
            return
    
    console.print(f"[bold green]🔄 Active model switched to:[/bold green] [bold cyan]{p['name']}[/bold cyan]")
    
    if DaemonSupervisor.is_running():
        console.print("[yellow]💡 Restarting daemon to load the new model into Metal GPU...[/yellow]")
        DaemonSupervisor.stop()
        DaemonSupervisor.start()
        console.print("[bold green]✅ Daemon reloaded with new model.[/bold green]")


@model_app.command(name="download")
def model_download(key: Optional[str] = typer.Argument(None, help="Model preset key to download")):
    """Downloads model weights with streaming progress."""
    target_key = key.strip().lower() if key else catalog.get_active_key()
    if target_key not in MODEL_PRESETS:
        console.print(f"[bold red]❌ Unknown preset:[/bold red] '{target_key}'. Available: {list(MODEL_PRESETS.keys())}")
        raise typer.Exit(1)

    preset = MODEL_PRESETS[target_key]
    if catalog.is_installed(target_key):
        console.print(f"[bold green]✅ '{preset['name']}' is already installed![/bold green]")
        catalog.set_active_key(target_key)
        return

    _download_model_with_progress(target_key)


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="Prompt or query to test against local AI"),
    system: Optional[str] = typer.Option("당신은 유능한 AI 어시스턴트입니다.", "--system", "-s", help="System prompt")
):
    """Sends a quick query to the active model via SkyBrain daemon or in-process engine."""
    import httpx
    if DaemonSupervisor.is_running():
        url = f"http://{settings.host}:{settings.port}/v1/chat/completions"
        try:
            resp = httpx.post(
                url,
                json={
                    "model": catalog.get_active_key(),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=60.0
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                console.print(f"\n[bold cyan]🤖 SkyBrain Response:[/bold cyan]\n{content}\n")
                return
        except Exception as e:
            console.print(f"[yellow]⚠️ Daemon API call failed ({e}), falling back to direct engine...[/yellow]")

    # Direct in-process fallback (ensure model is ready)
    active_key = catalog.get_active_key()
    if not catalog.is_installed(active_key):
        console.print(f"[bold yellow]⚠️ Model '{active_key}' not installed. Downloading before query...[/bold yellow]")
        _download_model_with_progress(active_key)

    from skybrain.server.app import get_llm
    llm = get_llm()
    combined = f"{system}\n\n[User]\n{prompt}"
    resp = llm.create_chat_completion(
        messages=[{"role": "user", "content": combined}],
        temperature=0.3,
        max_tokens=1024
    )
    content = resp["choices"][0]["message"]["content"]
    console.print(f"\n[bold cyan]🤖 SkyBrain Response (In-Process):[/bold cyan]\n{content}\n")


if __name__ == "__main__":
    app()

