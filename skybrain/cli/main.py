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
mcp_app = typer.Typer(name="mcp", help="Manage and run Model Context Protocol (MCP) server", invoke_without_command=True)
doc_app = typer.Typer(name="doc", help="Manage multi-project document intelligence and CAS index")
app.add_typer(model_app)
app.add_typer(mcp_app)
app.add_typer(doc_app)

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
    force: bool = typer.Option(False, "--force", "-f", help="Force terminate any stale processes and restart"),
    insecure: bool = typer.Option(False, "--insecure", "-k", help="Skip SSL certificate verification for downloads (Corporate MITM proxy fallback)"),
    ca_bundle: Optional[str] = typer.Option(None, "--ca-bundle", help="Custom CA certificate bundle path for corporate network")
):
    """Starts the background SkyBrain OpenAI-compatible serving daemon."""
    if insecure:
        settings.ssl_verify = False
    if ca_bundle:
        settings.ca_bundle = ca_bundle

    if DaemonSupervisor.is_running() and not force:
        console.print("[bold yellow]⚡ SkyBrain daemon is already running.[/bold yellow]")
        return

    active_key = catalog.get_active_key()

    # Pre-Flight 4-Tier Environment Check
    from skybrain.core.hardware import HardwareAutoTuner, EnvironmentTier
    assessment = HardwareAutoTuner.assess_environment(model_key=active_key)
    if assessment.tier == EnvironmentTier.INCOMPATIBLE and not force:
        console.print(f"\n[bold red]{assessment.title}[/bold red]")
        console.print(f"[red]{assessment.message}[/red]\n")
        console.print("[dim]Use '--force' if you want to bypass this check at your own risk.[/dim]")
        raise typer.Exit(1)
    elif assessment.tier == EnvironmentTier.CONSTRAINED:
        console.print(f"[bold yellow]{assessment.title}[/bold yellow]")
        console.print(f"[yellow]{assessment.message}[/yellow]\n")
    else:
        console.print(f"[bold green]{assessment.title}[/bold green]")

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
        console.print(f"• Auto-Tuned GPU Layers: [bold]{assessment.recommended_layers}[/bold] ({assessment.hardware.gpu_backend.upper()})")
    else:
        console.print("[bold red]❌ Failed to start SkyBrain daemon. Check ~/.skybrain/skybrain.log[/bold red]")
        raise typer.Exit(1)


@app.command()
def doctor(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Evaluate specifically for this model key")
):
    """Diagnoses host environment, RAM, VRAM, and evaluates 4-tier suitability for SkyBrain."""
    from skybrain.core.hardware import HardwareAutoTuner, EnvironmentTier
    active_key = model or catalog.get_active_key()
    hw = HardwareAutoTuner.detect_hardware()
    assessment = HardwareAutoTuner.assess_environment(model_key=active_key, hw=hw)

    table = Table(title="🏥 SkyBrain Pre-Flight System Diagnostic Report", header_style="bold cyan")
    table.add_column("Diagnostic Item", style="bold")
    table.add_column("Value / Status")

    # Operating System & Architecture
    table.add_row("OS / Platform", f"{hw.os_name} ({hw.architecture}) - {'64-bit' if hw.is_64bit else '32-bit'}")
    table.add_row("CPU Logical Cores", f"{hw.cpu_count} Cores")

    # Memory
    ram_style = "green" if hw.available_ram_gb >= 3.5 else ("yellow" if hw.available_ram_gb >= 2.0 else "bold red")
    table.add_row("Host RAM (Total / Avail)", f"[{ram_style}]{hw.total_ram_gb:.1f} GB / {hw.available_ram_gb:.1f} GB Available[/{ram_style}]")

    # GPU & VRAM
    gpu_style = "bold green" if hw.gpu_backend in ("metal", "cuda") else "yellow"
    table.add_row("Acceleration Engine", f"[{gpu_style}]{hw.gpu_name} ({hw.gpu_backend.upper()})[/{gpu_style}]")
    if hw.total_vram_gb is not None and hw.free_vram_gb is not None:
        vram_style = "green" if hw.free_vram_gb >= 3.0 else "yellow"
        table.add_row("VRAM (Total / Free)", f"[{vram_style}]{hw.total_vram_gb:.1f} GB / {hw.free_vram_gb:.1f} GB Free[/{vram_style}]")
    else:
        table.add_row("Dedicated VRAM", "[dim]N/A (Host RAM used via CPU)[/dim]")

    # Recommended GPU Layers
    table.add_row("Target Model", f"[bold]{active_key}[/bold]")
    table.add_row("Auto-Tuned GPU Layers", f"[bold cyan]{assessment.recommended_layers}[/bold cyan] ({'Full Offload' if assessment.recommended_layers == -1 else ('CPU Mode' if assessment.recommended_layers == 0 else f'{assessment.recommended_layers} Layers')})")

    # Environment Tier Evaluation
    tier_colors = {
        EnvironmentTier.ABUNDANT: "bold green",
        EnvironmentTier.OPTIMAL: "green",
        EnvironmentTier.CONSTRAINED: "bold yellow",
        EnvironmentTier.INCOMPATIBLE: "bold red",
    }
    tier_color = tier_colors.get(assessment.tier, "white")
    table.add_row("Capability Rating", f"[{tier_color}]{assessment.title}[/{tier_color}]")

    console.print(table)
    console.print(f"\n[{tier_color}]{assessment.message}[/{tier_color}]\n")


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

    # Host System Memory & Pre-flight Guard
    from skybrain.core.monitor import HostMemoryMonitor, MemoryStatusLevel
    from skybrain.core.hardware import HardwareAutoTuner, EnvironmentTier
    mem = HostMemoryMonitor.get_memory_info()
    if mem.status == MemoryStatusLevel.SAFE:
        mem_str = f"[green]🟢 Safe ({mem.available_gb:.1f} GB avail / {mem.total_gb:.1f} GB total)[/green]"
    elif mem.status == MemoryStatusLevel.WARNING:
        mem_str = f"[yellow]⚠️ Warning ({mem.available_gb:.1f} GB avail / {mem.total_gb:.1f} GB total - Low)[/yellow]"
    else:
        mem_str = f"[bold red]🚨 Critical ({mem.available_gb:.1f} GB avail - High Freeze Risk!)[/bold red]"
    table.add_row("Host RAM (Unified)", mem_str)

    # 4-Tier Pre-Flight Environment & GPU Layers
    env = HardwareAutoTuner.assess_environment(model_key=active_key)
    tier_colors = {
        EnvironmentTier.ABUNDANT: "bold green",
        EnvironmentTier.OPTIMAL: "green",
        EnvironmentTier.CONSTRAINED: "bold yellow",
        EnvironmentTier.INCOMPATIBLE: "bold red",
    }
    tier_color = tier_colors.get(env.tier, "white")
    table.add_row("Environment Rating", f"[{tier_color}]{env.title}[/{tier_color}]")
    layer_desc = "Full Offload" if env.recommended_layers == -1 else ("CPU Mode" if env.recommended_layers == 0 else f"{env.recommended_layers} Layers")
    table.add_row("GPU Layer Tuning", f"[bold]{env.recommended_layers}[/bold] ({layer_desc} via {env.hardware.gpu_backend.upper()})")
    table.add_row("System Guard", "[bold green]🛡️ Enabled[/bold green] (OOM Protection & Auto-Offload)")

    # Corporate Network & SSL Status
    ssl_status = "[green]Strict (Verified)[/green]" if settings.ssl_verify else "[yellow]Insecure (Unverified - Corporate Bypass)[/yellow]"
    if settings.ca_bundle:
        ssl_status += f" (CA: {settings.ca_bundle})"
    table.add_row("SSL Verification", ssl_status)

    import os
    proxy_info = settings.https_proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "-"
    table.add_row("Network Proxy", proxy_info)

    console.print(table)


@model_app.command(name="list")
def model_list():
    """Lists all available AI model presets, storage status, and real-time hardware suitability."""
    from skybrain.core.hardware import HardwareAutoTuner, EnvironmentTier
    presets = catalog.list_models()
    table = Table(title="🤖 SkyBrain AI Model Catalog & Hardware Suitability", header_style="bold magenta")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Model Name", style="bold")
    table.add_column("Context", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Status", style="bold")
    table.add_column("Active", justify="center")
    table.add_column("Hardware Capability", style="bold")
    table.add_column("GPU Layers", justify="center")

    tier_colors = {
        EnvironmentTier.ABUNDANT: "bold green",
        EnvironmentTier.OPTIMAL: "green",
        EnvironmentTier.CONSTRAINED: "bold yellow",
        EnvironmentTier.INCOMPATIBLE: "bold red",
    }

    for p in presets:
        status = "[green]Installed[/green]" if p["installed"] else "[dim]Not downloaded[/dim]"
        size_str = f"{p['size_mb']} MB" if p["installed"] else "-"
        active_str = "🟢 [bold green]YES[/bold green]" if p["active"] else "-"
        ctx_str = f"{p['context_length'] // 1024}k"

        env = HardwareAutoTuner.assess_environment(model_key=p["key"])
        tier_col = tier_colors.get(env.tier, "white")
        tier_short = env.title.split("]")[0] + "]"
        layers_str = "Full (-1)" if env.recommended_layers == -1 else ("CPU (0)" if env.recommended_layers == 0 else str(env.recommended_layers))

        table.add_row(p["key"], p["name"], ctx_str, size_str, status, active_str, f"[{tier_col}]{tier_short}[/{tier_col}]", layers_str)

    console.print(table)
    console.print("\n[dim]Commands: 'skybrain model download [key]' | 'skybrain model use [key]'[/dim]")


@model_app.command(name="use")
def model_use(
    key: str = typer.Argument(..., help="Model preset key to activate"),
    auto_download: bool = typer.Option(True, "--auto-download/--no-auto-download", "-d/-nd", help="Automatically download model if missing"),
    force: bool = typer.Option(False, "--force", "-f", help="Force activation even if hardware capacity is critically low")
):
    """Switches the active AI model with pre-flight hardware safety guard."""
    clean_key = key.strip().lower()
    if clean_key not in MODEL_PRESETS:
        console.print(f"[bold red]❌ Unknown preset:[/bold red] '{clean_key}'. Available: {list(MODEL_PRESETS.keys())}")
        raise typer.Exit(1)

    from skybrain.core.hardware import HardwareAutoTuner, EnvironmentTier
    env = HardwareAutoTuner.assess_environment(model_key=clean_key)
    if env.tier == EnvironmentTier.INCOMPATIBLE and not force:
        console.print(f"\n[bold red]{env.title}[/bold red]")
        console.print(f"[red]{env.message}[/red]\n")
        console.print("[dim]Use '--force' to bypass this safety guard at your own risk.[/dim]")
        raise typer.Exit(1)
    elif env.tier == EnvironmentTier.CONSTRAINED:
        console.print(f"[bold yellow]{env.title}[/bold yellow]")

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
def model_download(
    key: Optional[str] = typer.Argument(None, help="Model preset key to download"),
    force: bool = typer.Option(False, "--force", "-f", help="Force download even if hardware capacity is critically low"),
    insecure: bool = typer.Option(False, "--insecure", "-k", help="Skip SSL certificate verification for corporate MITM proxies"),
    ca_bundle: Optional[str] = typer.Option(None, "--ca-bundle", help="Custom CA certificate bundle path for corporate network")
):
    """Downloads model weights with pre-flight capability assessment and streaming progress."""
    if insecure:
        settings.ssl_verify = False
    if ca_bundle:
        settings.ca_bundle = ca_bundle

    target_key = key.strip().lower() if key else catalog.get_active_key()
    if target_key not in MODEL_PRESETS:
        console.print(f"[bold red]❌ Unknown preset:[/bold red] '{target_key}'. Available: {list(MODEL_PRESETS.keys())}")
        raise typer.Exit(1)

    from skybrain.core.hardware import HardwareAutoTuner, EnvironmentTier
    env = HardwareAutoTuner.assess_environment(model_key=target_key)
    if env.tier == EnvironmentTier.INCOMPATIBLE and not force:
        console.print(f"\n[bold red]{env.title}[/bold red]")
        console.print(f"[red]{env.message}[/red]\n")
        console.print("[dim]Use '--force' to bypass this safety guard at your own risk.[/dim]")
        raise typer.Exit(1)
    elif env.tier == EnvironmentTier.CONSTRAINED:
        console.print(f"[bold yellow]{env.title}[/bold yellow]")

    preset = MODEL_PRESETS[target_key]
    if catalog.is_installed(target_key):
        console.print(f"[bold green]✅ '{preset['name']}' is already installed![/bold green]")
        catalog.set_active_key(target_key)
        return

    _download_model_with_progress(target_key)


@app.command()
def query(
    prompt: str = typer.Argument(..., help="Prompt to run directly on local SLM"),
    system: Optional[str] = typer.Option(None, "--system", "-s", help="Optional system prompt"),
    temperature: float = typer.Option(0.3, "--temperature", "-t", help="Sampling temperature"),
    max_tokens: int = typer.Option(1024, "--max-tokens", "-m", help="Maximum output tokens"),
):
    """Directly queries the local on-device SLM with zero cloud network calls."""
    active_key = catalog.get_active_key()
    if not catalog.is_installed(active_key):
        console.print(f"[bold yellow]⚠️ Model '{active_key}' not installed. Auto-downloading...[/bold yellow]")
        _download_model_with_progress(active_key)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    from skybrain.server.supervisor import DaemonSupervisor
    import httpx

    content = None
    with console.status(f"[bold cyan]Running on-device inference ({active_key})...[/bold cyan]"):
        if DaemonSupervisor.check_health_fast():
            try:
                url = f"http://{settings.host}:{settings.port}/v1/chat/completions"
                payload = {
                    "model": active_key,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                resp = httpx.post(url, json=payload, timeout=120.0)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                logger.debug(f"Daemon HTTP query failed, falling back to direct engine: {e}")

        if content is None:
            from skybrain.server.app import get_llm, close_llm
            try:
                llm = get_llm()
                resp = llm.create_chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = resp["choices"][0]["message"]["content"]
            finally:
                close_llm()

    console.print(f"\n[bold green][⚡ On-Device SLM: {active_key}][/bold green]")
    console.print(f"[cyan]{content}[/cyan]\n")


@app.command(name="review")
def review_cmd(
    target: str = typer.Argument(".", help="Target file or directory to review"),
    rounds: int = typer.Option(1, "--rounds", "-r", help="Voting rounds per lens (1 for fast, 3 for consensus)"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Run Chain-of-Thought verification on findings"),
    use_cache: bool = typer.Option(True, "--cache/--no-cache", help="Use content-hash result cache"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output machine-parsable JSON for Lead LLM cross-checking"),
):
    """Executes Multi-Lens Pre-Screening Review and outputs findings optimized for Lead LLM cross-checking."""
    from pathlib import Path
    from skybrain.review.engine import ReviewEngine
    from skybrain.review.lenses.clean_code import CleanCodeLens
    from skybrain.review.lenses.clean_architecture import CleanArchitectureLens
    from skybrain.review.lenses.security import SecurityLens
    from skybrain.review.lenses.performance import PerformanceLens
    from skybrain.review.lenses.ai_conduct import AIConductLens
    from skybrain.review.lenses.resilience import ResilienceLens

    target_path = Path(target).resolve()
    if target_path.is_file():
        files_to_review = [target_path]
    elif target_path.is_dir():
        # Collect source files (.py, .kt, .java)
        extensions = ("*.py", "*.kt", "*.java")
        files_to_review = [
            p for ext in extensions for p in target_path.rglob(ext)
            if not any(part.startswith((".", "__")) or part in ("build", "dist", "site-packages", ".gradle") for part in p.parts)
        ]
    else:
        console.print(f"[bold red]❌ Target path not found: {target}[/bold red]")
        raise typer.Exit(1)

    if not files_to_review:
        console.print("[yellow]⚠️ No reviewable source files found.[/yellow]")
        return

    if not json_output:
        console.print(f"\n[bold cyan]🔍 SkyBrain Multi-Lens Code Review (6-Lens System)[/bold cyan]")
        console.print(f"[dim]Target: {target} ({len(files_to_review)} files) | Rounds: {rounds} | Verification: {verify}[/dim]")
        console.print("[dim]Active Lenses: CleanCode, CleanArchitecture, Security, Performance, AIConduct, Resilience[/dim]")

    # ── Pre-flight System & Memory Guard ──
    from skybrain.core.monitor import SystemGuard, MemoryStatusLevel
    mem_eval = SystemGuard.evaluate(has_cloud_fallback=False)
    if mem_eval.status == MemoryStatusLevel.CRITICAL and not mem_eval.allowed:
        console.print(f"\n[bold red]{mem_eval.message}[/bold red]\n")
        raise typer.Exit(1)
    elif mem_eval.status == MemoryStatusLevel.WARNING and not json_output:
        console.print(f"[yellow]⚠️ {mem_eval.message}[/yellow]\n")
    elif not json_output:
        console.print(f"[dim]🧠 Memory Guard: Safe ({mem_eval.available_gb:.1f} GB available)[/dim]\n")

    # ── Daemon Auto-Healing Check ──
    from skybrain.server.supervisor import DaemonSupervisor
    DaemonSupervisor.ensure_daemon_alive()

    lenses = [
        CleanCodeLens,
        CleanArchitectureLens,
        SecurityLens,
        PerformanceLens,
        AIConductLens,
        ResilienceLens,
    ]
    engine = ReviewEngine(lens_classes=lenses)

    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )

    total_lens_steps = len(files_to_review) * len(lenses)

    if json_output or not console.is_terminal:
        report = engine.review(
            file_paths=files_to_review,
            verify=verify,
            voting_rounds=rounds,
            use_cache=use_cache,
        )
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}[/bold cyan]"),
            BarColumn(bar_width=35),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("• ETA:"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Starting inspection...", total=total_lens_steps)

            def _on_progress(desc: str, advance_amt: float):
                progress.update(task_id, description=desc, advance=advance_amt)

            report = engine.review(
                file_paths=files_to_review,
                verify=verify,
                voting_rounds=rounds,
                use_cache=use_cache,
                progress_callback=_on_progress,
            )

    if json_output:
        import json
        console.print(json.dumps(report.to_lead_llm_payload(), indent=2, ensure_ascii=False))
        import os
        os._exit(0)

    # Render Report Table
    table = Table(title="📋 SkyBrain Multi-Lens Review Findings", header_style="bold magenta")
    table.add_column("Severity", style="bold", width=10)
    table.add_column("Lens / Principle", width=25)
    table.add_column("Location", width=25)
    table.add_column("Description & Suggestion")

    sev_styles = {
        "CRITICAL": "bold red",
        "HIGH": "red",
        "MEDIUM": "yellow",
        "LOW": "blue",
        "INFO": "dim",
    }

    findings = report.findings
    if not findings:
        console.print(f"[bold green]🎉 Perfect! No defects found across all {len(lenses)} lenses.[/bold green]\n")
    else:
        for f in findings:
            sev_str = f.severity.name if hasattr(f.severity, "name") else str(f.severity)
            style = sev_styles.get(sev_str.upper(), "white")
            loc_str = f"{Path(f.file).name}:{f.line}"
            desc_sugg = f"{f.description}\n[dim]👉 {f.suggestion}[/dim]" if f.suggestion else f.description
            table.add_row(
                f"[{style}]{sev_str}[/{style}]",
                f.principle_violated,
                loc_str,
                desc_sugg,
            )

        console.print(table)
        console.print(f"\n[bold green]Health Score: {report.health_score}/100[/bold green] | [dim]Summary: Total {len(findings)} findings across {len(report.files_reviewed)} files in {report.total_duration_seconds:.2f}s[/dim]")
        console.print("[dim]💡 Tip: Use 'skybrain review <path> --json' to export structured payload for Lead LLM (Gemini/Claude) cross-check.[/dim]\n")

    import os
    os._exit(0)


@mcp_app.callback(invoke_without_command=True)
def mcp_callback(ctx: typer.Context):
    """Starts the Model Context Protocol (MCP) server or manages MCP integration."""
    if ctx.invoked_subcommand is None:
        from skybrain.mcp.server import main as mcp_main
        mcp_main()


@mcp_app.command(name="run")
def mcp_run():
    """Starts the Model Context Protocol (MCP) server in stdio mode."""
    from skybrain.mcp.server import main as mcp_main
    mcp_main()


@mcp_app.command(name="tools")
def mcp_tools():
    """Lists all available SkyBrain MCP tools and parameters."""
    from skybrain.mcp.server import TOOLS
    table = Table(title="🛠️ SkyBrain MCP Tools (stdio)", header_style="bold cyan")
    table.add_column("Tool Name", style="bold green", no_wrap=True)
    table.add_column("Description")
    table.add_column("Required Args", style="dim")

    for t in TOOLS:
        schema = t.get("inputSchema", {})
        req = ", ".join(schema.get("required", [])) or "(none)"
        table.add_row(t["name"], t["description"], req)

    console.print(table)


@mcp_app.command(name="setup")
def mcp_setup():
    """Prints copy-paste ready MCP configuration for Claude Code and Antigravity."""
    import json
    console.print("[bold cyan]🚀 SkyBrain MCP Integration Setup[/bold cyan]\n")

    console.print("[bold green]1. Anthropic Claude CLI (Claude Code):[/bold green]")
    console.print("Register SkyBrain directly in Claude Code with this single command:")
    console.print("  [bold yellow]claude mcp add skybrain -- uv tool run skybrain-mcp[/bold yellow]\n")

    console.print("[bold green]2. Antigravity IDE / Cursor / Claude Desktop:[/bold green]")
    config = {
        "mcpServers": {
            "skybrain": {
                "command": "uv",
                "args": ["tool", "run", "skybrain-mcp"]
            }
        }
    }
    console.print("Add to your MCP configuration (e.g. ~/.gemini/antigravity-ide/mcp_config.json or Claude settings):")
    console.print(f"[dim]{json.dumps(config, indent=2)}[/dim]\n")
    console.print("[dim]💡 SkyBrain MCP provides on-device zero-cost translation, log summarization, code review, and consensus.[/dim]")


# ==============================================================================
# Document Intelligence & Multi-Project CAS Commands
# ==============================================================================

@doc_app.command(name="add")
def doc_add(
    path: str = typer.Argument(..., help="Directory path to index"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name (defaults to folder name)"),
):
    """Adds a directory as a project and scans all documents with CAS deduplication."""
    from skybrain.store.manager import DocumentManager
    manager = DocumentManager()

    console.print(f"[bold cyan]🔍 Scanning and indexing project directory:[/bold cyan] {path}")
    try:
        stats = manager.add_project(path, name=name)
        console.print(f"[bold green]✅ Successfully indexed project:[/bold green] [bold yellow]{stats['project_name']}[/bold yellow] (ID: {stats['project_id']})")
        table = Table(title="📊 Indexing Summary", header_style="bold cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Count", style="green")
        table.add_row("Scanned Files", str(stats["scanned_files"]))
        table.add_row("New Files Added", str(stats["added_files"]))
        table.add_row("Reused (Deduplicated)", str(stats["reused_files"]))
        table.add_row("Updated Files", str(stats["updated_files"]))
        table.add_row("New Chunks Stored", str(stats["new_chunks"]))
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]❌ Failed to add project:[/bold red] {e}")
        raise typer.Exit(1)


@doc_app.command(name="sync")
def doc_sync(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Specific project ID to sync (defaults to all)"),
):
    """Performs incremental sync for registered projects."""
    from skybrain.store.manager import DocumentManager
    manager = DocumentManager()

    console.print(f"[bold cyan]🔄 Running incremental sync...[/bold cyan]")
    results = manager.sync_project(project)
    if not results:
        console.print("[yellow]No registered projects found to sync.[/yellow]")
        return

    for stats in results:
        console.print(f"\n[bold green]📁 Project:[/bold green] {stats['project_name']} (Scanned: {stats['scanned_files']}, Added: {stats['added_files']}, Reused: {stats['reused_files']}, Updated: {stats['updated_files']})")


@doc_app.command(name="list")
def doc_list():
    """Lists all registered projects and indexing statistics."""
    from skybrain.store.manager import DocumentManager
    manager = DocumentManager()

    projects = manager.list_projects()
    if not projects:
        console.print("[yellow]No projects registered yet. Use `skybrain doc add <path>` to add one.[/yellow]")
        return

    table = Table(title="📚 Registered Projects & Knowledge Hub", header_style="bold cyan")
    table.add_column("Project ID", style="bold yellow")
    table.add_column("Name", style="bold")
    table.add_column("Active Files", justify="right", style="green")
    table.add_column("Root Path", style="dim")
    table.add_column("Registered At", style="dim")

    for p in projects:
        table.add_row(p["id"], p["name"], str(p["active_files"]), p["root_path"], str(p["created_at"]))

    console.print(table)


@doc_app.command(name="search")
def doc_search(
    query: str = typer.Argument(..., help="Search query"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID to filter by"),
    limit: int = typer.Option(5, "--limit", "-l", help="Maximum number of results"),
):
    """Searches document chunks using SQLite FTS5 and project lexicon expansion."""
    from skybrain.store.manager import DocumentManager
    manager = DocumentManager()

    console.print(f"[bold cyan]🔎 Searching knowledge base for:[/bold cyan] '{query}'" + (f" in project [yellow]{project}[/yellow]" if project else " (cross-project)"))
    results = manager.search(query, project_id=project, limit=limit)

    if not results:
        console.print("[yellow]No matching documents found.[/yellow]")
        return

    for idx, r in enumerate(results, start=1):
        console.print(f"\n[bold green]#{idx} [{r['project_id']}] {r['relative_path']}[/bold green] (Rank: {r['rank']:.2f})")
        if r["heading_hierarchy"]:
            console.print(f"   [dim cyan]📍 {r['heading_hierarchy']}[/dim cyan]")
        snippet = r["chunk_text"][:300].replace("\n", " ")
        if len(r["chunk_text"]) > 300:
            snippet += "..."
        console.print(f"   {snippet}")


if __name__ == "__main__":
    app()


