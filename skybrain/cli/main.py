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
config_app = typer.Typer(name="config", help="Manage SkyBrain Gateway and cloud endpoints/keys")
app.add_typer(model_app)
app.add_typer(config_app)

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

    # Host System Memory & Pre-flight Guard
    from skybrain.core.monitor import HostMemoryMonitor, MemoryStatusLevel
    mem = HostMemoryMonitor.get_memory_info()
    if mem.status == MemoryStatusLevel.SAFE:
        mem_str = f"[green]🟢 Safe ({mem.available_gb:.1f} GB avail / {mem.total_gb:.1f} GB total)[/green]"
    elif mem.status == MemoryStatusLevel.WARNING:
        mem_str = f"[yellow]⚠️ Warning ({mem.available_gb:.1f} GB avail / {mem.total_gb:.1f} GB total - Low)[/yellow]"
    else:
        mem_str = f"[bold red]🚨 Critical ({mem.available_gb:.1f} GB avail - High Freeze Risk!)[/bold red]"
    table.add_row("Host RAM (Unified)", mem_str)
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
def model_download(
    key: Optional[str] = typer.Argument(None, help="Model preset key to download"),
    insecure: bool = typer.Option(False, "--insecure", "-k", help="Skip SSL certificate verification for corporate MITM proxies"),
    ca_bundle: Optional[str] = typer.Option(None, "--ca-bundle", help="Custom CA certificate bundle path for corporate network")
):
    """Downloads model weights with streaming progress."""
    if insecure:
        settings.ssl_verify = False
    if ca_bundle:
        settings.ca_bundle = ca_bundle

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
    system: Optional[str] = typer.Option("You are a helpful and expert AI assistant.", "--system", "-s", help="System prompt"),
    cloud: bool = typer.Option(False, "--cloud", "-c", help="Force cloud routing (with auto-failover to local SkyBrain on quota/overload)"),
    api_url: Optional[str] = typer.Option(None, "--api-url", "-u", help="Custom AI API address (e.g. http://host:port/v1 or http://ai.corp.internal:8000)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="Cloud or custom API key/token"),
    api_model: Optional[str] = typer.Option(None, "--api-model", "-m", help="Target model identifier for custom/cloud API"),
    context: bool = typer.Option(True, "--context/--no-context", help="Include recent conversation context"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show routing decision details"),
):
    """Sends a query with intelligent local/cloud routing via the SkyBrain Gateway.

    By default, uses rule-based classification to determine whether to
    process locally (zero cloud tokens) or escalate to cloud/custom LLM.
    If Custom/Cloud API experiences Quota Exceeded (429) or Overloaded (503),
    the Circuit Breaker automatically fails over to on-device SkyBrain.
    """
    import os

    # If user provided a custom API URL on the CLI
    if api_url:
        os.environ["CUSTOM_API_URL"] = api_url.strip()
        if verbose:
            console.print(f"[dim]🌐 Using Custom AI Address: {api_url}[/dim]")

    if api_model:
        clean_model = api_model.strip()
        os.environ["CUSTOM_API_MODEL"] = clean_model
        os.environ["GEMINI_MODEL"] = clean_model

    # If user provided an API key on the CLI, auto-detect provider format
    if api_key:
        clean_key = api_key.strip()
        if api_url:
            os.environ["CUSTOM_API_KEY"] = clean_key
        elif clean_key.startswith("AIzaSy"):
            os.environ["GEMINI_API_KEY"] = clean_key
            if verbose:
                console.print("[dim]🔑 Detected Google Gemini API Key[/dim]")
        elif clean_key.startswith("sk-ant-"):
            os.environ["ANTHROPIC_API_KEY"] = clean_key
            if verbose:
                console.print("[dim]🔑 Detected Anthropic Claude API Key[/dim]")
        elif clean_key.startswith("sk-"):
            os.environ["OPENAI_API_KEY"] = clean_key
            if verbose:
                console.print("[dim]🔑 Detected OpenAI API Key[/dim]")
        else:
            # Default to Gemini if unsure
            os.environ["GEMINI_API_KEY"] = clean_key

    from skybrain.gateway import (
        SmartRoutingProxy,
        IntentClassifier,
        ConversationHistory,
        RoutingStats,
    )

    classifier = IntentClassifier()
    history = ConversationHistory()
    stats = RoutingStats()
    proxy = SmartRoutingProxy(classifier=classifier, history=history, stats=stats)

    classification = classifier.classify(prompt)

    if verbose:
        console.print(f"[dim]🧠 Routing Decision: target={classification.target.value}, "
                       f"confidence={classification.confidence:.0%}, "
                       f"rule={classification.matched_rule or 'none'}, "
                       f"reason={classification.reason}[/dim]")

    # Helper: local executor via daemon or in-process fallback
    def _local_exec(messages, system_prompt, temperature, max_tokens):
        import httpx
        DaemonSupervisor.ensure_daemon_alive()
        if DaemonSupervisor.is_running():
            url = f"http://{settings.host}:{settings.port}/v1/chat/completions"
            try:
                resp = httpx.post(
                    url,
                    json={
                        "model": catalog.get_active_key(),
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=60.0
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                console.print(f"[yellow]⚠️ Daemon call failed ({e}), falling back to direct engine...[/yellow]")

        active_key = catalog.get_active_key()
        if not catalog.is_installed(active_key):
            console.print(f"[bold yellow]⚠️ Model '{active_key}' not installed. Downloading before query...[/bold yellow]")
            _download_model_with_progress(active_key)

        from skybrain.server.app import get_llm
        llm = get_llm()
        combined = f"{system_prompt or ''}\n\n[User]\n{prompt}"
        resp = llm.create_chat_completion(
            messages=[{"role": "user", "content": combined}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp["choices"][0]["message"]["content"]

    # Execute through SmartRoutingProxy
    with console.status("[bold cyan]Processing query via SkyBrain Gateway...[/bold cyan]"):
        result = proxy.route_and_generate(
            prompt=prompt,
            system_prompt=system,
            force_cloud=cloud,
            include_context=context,
            local_fallback_executor=_local_exec,
        )

    # Display response with clear processing engine and version badge
    engine_str = result.get("engine", "SkyBrain")
    is_fail = result.get("is_failover", False)

    if is_fail:
        badge_style = "bold yellow"
        icon = "🛡️"
    elif "Cloud" in engine_str:
        badge_style = "bold blue"
        icon = "☁️"
    elif "Custom" in engine_str:
        badge_style = "bold magenta"
        icon = "🌐"
    else:
        badge_style = "bold green"
        icon = "⚡"

    console.print(f"\n[{badge_style}][{icon} Processing Engine: {engine_str}][/{badge_style}]")
    console.print(f"[bold cyan]🤖 Response:[/bold cyan]\n{result.get('content')}\n")

    # Clean fast-exit to avoid upstream llama.cpp Metal teardown assertion crash
    # See: https://github.com/ggml-org/llama.cpp/pull/17869
    import os
    os._exit(0)


@config_app.command(name="list")
def config_list():
    """Lists current Cloud LLM endpoints, models, and API key status."""
    import os

    table = Table(title="⚙️ SkyBrain Gateway & Cloud Configuration", header_style="bold cyan")
    table.add_column("Property", style="bold")
    table.add_column("Value")
    table.add_column("Source", style="dim")

    def _mask_key(key: Optional[str]) -> str:
        if not key:
            return "[dim]Not set[/dim]"
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    # Gemini
    gem_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    gem_src = "env: GEMINI_API_KEY" if os.environ.get("GEMINI_API_KEY") else ("config.json" if settings.gemini_api_key else "none")
    table.add_row("Gemini API Key", _mask_key(gem_key), gem_src)

    gem_endpoint = os.environ.get("GEMINI_ENDPOINT") or settings.gemini_endpoint
    table.add_row("Gemini Endpoint", gem_endpoint, "custom" if os.environ.get("GEMINI_ENDPOINT") else "default")

    gem_model = os.environ.get("GEMINI_MODEL") or settings.gemini_model
    table.add_row("Gemini Model", gem_model, "custom" if os.environ.get("GEMINI_MODEL") else "default")

    # OpenAI
    oa_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY")
    oa_src = "env: OPENAI_API_KEY" if os.environ.get("OPENAI_API_KEY") else ("config.json" if settings.openai_api_key else "none")
    table.add_row("OpenAI API Key", _mask_key(oa_key), oa_src)
    table.add_row("OpenAI Base URL", settings.openai_base_url, "default")

    # Claude
    cl_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    cl_src = "env: ANTHROPIC_API_KEY" if os.environ.get("ANTHROPIC_API_KEY") else ("config.json" if settings.anthropic_api_key else "none")
    table.add_row("Claude API Key", _mask_key(cl_key), cl_src)

    # Custom API URL
    custom_url = settings.custom_api_url or os.environ.get("CUSTOM_API_URL")
    custom_src = "env: CUSTOM_API_URL" if os.environ.get("CUSTOM_API_URL") else ("config.json" if settings.custom_api_url else "none")
    table.add_row("Custom AI Address (URL)", custom_url or "[dim]Not set[/dim]", custom_src)

    # SSL / CA
    table.add_row("SSL Verification", "Strict (Verified)" if settings.ssl_verify else "Insecure (Bypassed)", "setting")
    if settings.ca_bundle:
        table.add_row("Custom CA Bundle", settings.ca_bundle, "setting")

    console.print(table)
    console.print("\n[dim]Set values with: 'skybrain config set <key> <value>'[/dim]")
    console.print("[dim]Supported keys: custom_api_url, custom_api_key, custom_api_model, gemini_api_key, gemini_endpoint, gemini_model, openai_api_key, openai_base_url, anthropic_api_key[/dim]")


@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key (e.g. gemini_api_key, gemini_endpoint, gemini_model)"),
    value: str = typer.Argument(..., help="Configuration value")
):
    """Persistently sets a configuration option in ~/.skybrain/config.json."""
    import json
    config_file = settings.home_dir / "config.json"
    data = {}
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    clean_key = key.strip().lower()
    data[clean_key] = value.strip()
    config_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    console.print(f"[bold green]✔ Config saved:[/bold green] [cyan]{clean_key}[/cyan] = [dim]{value[:6]}...[/dim] (in {config_file})")


@app.command(name="review")
def review_cmd(
    target: str = typer.Argument(".", help="Target file or directory to review"),
    rounds: int = typer.Option(1, "--rounds", "-r", help="Voting rounds per lens (1 for fast, 3 for consensus)"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Run Chain-of-Thought verification on findings"),
    use_cache: bool = typer.Option(True, "--cache/--no-cache", help="Use content-hash result cache"),
    html: bool = typer.Option(True, "--html/--no-html", help="Generate standalone interactive HTML report"),
    output_html: Optional[str] = typer.Option(None, "--html-out", help="Custom output path for HTML report"),
):
    """Executes Multi-Lens Code Review with CleanCode, Architecture, Security, and Performance lenses."""
    from pathlib import Path
    from skybrain.review.engine import ReviewEngine
    from skybrain.review.lenses.clean_code import CleanCodeLens
    from skybrain.review.lenses.clean_architecture import CleanArchitectureLens
    from skybrain.review.lenses.security import SecurityLens
    from skybrain.review.lenses.performance import PerformanceLens
    from skybrain.review.lenses.ai_conduct import AIConductLens

    target_path = Path(target).resolve()
    if target_path.is_file():
        files_to_review = [target_path]
    elif target_path.is_dir():
        # Collect Python source files
        files_to_review = [
            p for p in target_path.rglob("*.py")
            if not any(part.startswith((".", "__")) or part in ("build", "dist", "site-packages") for part in p.parts)
        ]
    else:
        console.print(f"[bold red]❌ Target path not found: {target}[/bold red]")
        raise typer.Exit(1)

    if not files_to_review:
        console.print("[yellow]⚠️ No reviewable source files found.[/yellow]")
        return

    console.print(f"\n[bold cyan]🔍 SkyBrain Multi-Lens Code Review[/bold cyan]")
    console.print(f"[dim]Target: {target} ({len(files_to_review)} files) | Rounds: {rounds} | Verification: {verify}[/dim]")
    console.print("[dim]Active Lenses: CleanCode, CleanArchitecture, Security, Performance, AIConduct[/dim]")

    # ── Pre-flight System & Memory Guard ──
    from skybrain.core.monitor import SystemGuard, MemoryStatusLevel
    import os
    has_cloud = bool(settings.gemini_api_key or settings.openai_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    mem_eval = SystemGuard.evaluate(has_cloud_fallback=has_cloud)
    if mem_eval.status == MemoryStatusLevel.CRITICAL and not mem_eval.allowed:
        console.print(f"\n[bold red]{mem_eval.message}[/bold red]\n")
        raise typer.Exit(1)
    elif mem_eval.status == MemoryStatusLevel.WARNING:
        console.print(f"[yellow]⚠️ {mem_eval.message}[/yellow]\n")
    else:
        console.print(f"[dim]🧠 Memory Guard: Safe ({mem_eval.available_gb:.1f} GB available)[/dim]\n")

    # ── Daemon Auto-Healing Check ──
    from skybrain.server.supervisor import DaemonSupervisor
    DaemonSupervisor.ensure_daemon_alive()

    lenses = [CleanCodeLens, CleanArchitectureLens, SecurityLens, PerformanceLens, AIConductLens]
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
        console.print(f"\n[dim]Summary: Total {len(findings)} findings across {len(report.files_reviewed)} files reviewed in {report.total_duration_seconds:.2f}s[/dim]")

    if html:
        from skybrain.review.html_report import generate_html_report
        out_p = Path(output_html).resolve() if output_html else None
        html_file = generate_html_report(report, target_label=str(target), output_path=out_p)
        console.print(f"\n[bold green]📄 Interactive HTML Report saved:[/bold green] [cyan]file://{html_file}[/cyan]")
        console.print(f"[dim]💡 Open in browser with: [bold]open \"{html_file}\"[/bold][/dim]\n")

    import os
    os._exit(0)


@app.command()
def mcp():
    """Starts the Model Context Protocol (MCP) server for VS Code, Cursor, Cline, and Claude Desktop."""
    from skybrain.mcp.server import main as mcp_main
    mcp_main()


if __name__ == "__main__":
    app()

