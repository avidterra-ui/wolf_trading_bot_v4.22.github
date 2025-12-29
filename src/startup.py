"""
Interactive startup configuration for Wolf Trading Bot v4.1.
Provides colored menu and configuration on every launch.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, FloatPrompt, IntPrompt
from rich import box

from .models import RuntimeConfig, TPSLMode


console = Console()


def display_banner():
    """Display the startup banner."""
    console.clear()
    banner = """
[bold cyan]
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     🐺 WOLF TRADING BOT v4.1                                  ║
    ║     Telegram → BingX Auto-Trading System                      ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
[/bold cyan]
    """
    console.print(banner)


def display_security_info():
    """Display security information about bot permissions."""
    telegram_permissions = """
[bold yellow]TELEGRAM PERMISSIONS[/bold yellow]
[green]✅[/green] READ messages from: THE WOLF (CRYPTO)®
[red]❌[/red] CANNOT read your private messages
[red]❌[/red] CANNOT read other channels/groups
[red]❌[/red] CANNOT send messages
[red]❌[/red] CANNOT access contacts
    """
    
    bingx_permissions = """
[bold yellow]BINGX API PERMISSIONS[/bold yellow]
[green]✅[/green] CAN place futures trades (LIMIT ORDERS ONLY)
[green]✅[/green] CAN set leverage
[green]✅[/green] CAN check available balance
[green]✅[/green] CAN read market prices
[red]❌[/red] CANNOT withdraw funds
[red]❌[/red] CANNOT access wallet
[red]❌[/red] CANNOT transfer funds
[bold red]⚠️  NO MARKET ORDERS - Only Limit Orders allowed[/bold red]
    """
    
    console.print(Panel(
        telegram_permissions + "\n" + bingx_permissions,
        title="[bold]Security & Permissions[/bold]",
        border_style="blue"
    ))


async def interactive_startup() -> RuntimeConfig:
    """
    Interactive startup configuration.
    Runs on EVERY bot startup.
    
    Returns:
        RuntimeConfig with user-selected settings
    """
    display_banner()
    display_security_info()
    
    console.print("\n[dim]Press Enter to continue with configuration...[/dim]")
    input()
    
    config = RuntimeConfig()
    
    # ═══════════════════════════════════════════════════════════════
    # SECTION 1: Signal Sources
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]═══ SIGNAL SOURCES ═══[/bold yellow]\n")
    
    config.enable_vip_signals = Confirm.ask(
        "[cyan]Enable VIP signals (forwarded from WOLF OFFICIAL VIP)?[/cyan]",
        default=True
    )
    
    config.enable_free_signals = Confirm.ask(
        "[cyan]Enable FREE signals (direct posts)?[/cyan]",
        default=True
    )
    
    if not config.enable_vip_signals and not config.enable_free_signals:
        console.print("[bold red]❌ ERROR: At least one signal source must be enabled![/bold red]")
        console.print("[yellow]Restarting configuration...[/yellow]\n")
        return await interactive_startup()  # Restart
    
    # ═══════════════════════════════════════════════════════════════
    # SECTION 2: Position Sizing
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]═══ POSITION SIZING ═══[/bold yellow]\n")
    console.print("[dim]Your capital: ~$50 | Recommended: $1 per trade with 50× leverage[/dim]")
    console.print("[dim]$1 position × 50× leverage = $50 effective exposure[/dim]\n")
    
    config.position_size_usdt = FloatPrompt.ask(
        "[cyan]Position size per trade (USDT)[/cyan]",
        default=1.0
    )
    
    config.leverage = IntPrompt.ask(
        "[cyan]Leverage multiplier[/cyan]",
        default=50
    )
    
    # ═══════════════════════════════════════════════════════════════
    # SECTION 3: Daily Limits
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]═══ DAILY TRADE LIMITS ═══[/bold yellow]\n")
    console.print("[dim]Protect your capital by limiting total daily trades.[/dim]")
    console.print("[dim]This helps manage risk and prevent overtrading.[/dim]\n")
    
    config.max_trades_per_day = IntPrompt.ask(
        "[cyan]Maximum trades per day (total across all symbols)[/cyan]",
        default=5
    )
    
    if config.max_trades_per_day == 0:
        console.print("[yellow]⚠️  Unlimited daily trades - be careful![/yellow]")
    else:
        console.print(f"[green]✓ Maximum {config.max_trades_per_day} trades per day[/green]")
    
    # ═══════════════════════════════════════════════════════════════
    # SECTION 4: TP/SL Strategy (Separate for VIP and FREE)
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]═══ TP/SL STRATEGY ═══[/bold yellow]\n")
    
    console.print("[dim]TP/SL percentages are entered WITHOUT leverage:[/dim]")
    console.print(f"[dim]  • 1% without leverage = {config.leverage}% with {config.leverage}× leverage[/dim]")
    console.print(f"[dim]  • Default TP: 10% without leverage ({10 * config.leverage}% with leverage)[/dim]")
    console.print(f"[dim]  • [bold red]Max SL: 5% without leverage ({5 * config.leverage}% with leverage) - HARD CAP[/bold red][/dim]\n")
    
    # VIP TP/SL Mode (Always Manual)
    console.print("[bold cyan]VIP Signal TP/SL Mode:[/bold cyan]")
    console.print("[yellow]VIP signals do not contain TP/SL data - always uses MANUAL percentages[/yellow]")
    config.vip_tp_sl_mode = TPSLMode.MANUAL
    console.print("[green]✓ VIP signals will use MANUAL TP/SL percentages[/green]\n")
    
    # FREE TP/SL Mode (User choice: from_signal or manual)
    if config.enable_free_signals:
        console.print("[bold cyan]FREE Signal TP/SL Mode:[/bold cyan]")
        console.print("[dim]FREE signals may contain TP/SL values in the text/image.[/dim]")
        
        free_mode = Prompt.ask(
            "[cyan]FREE signal TP/SL mode[/cyan]",
            choices=["from_signal", "manual"],
            default="from_signal"
        )
        config.free_tp_sl_mode = TPSLMode(free_mode)
        
        if free_mode == "from_signal":
            console.print("[green]✓ FREE signals will use TP/SL from signal text/image[/green]")
            console.print("[dim]  If TP/SL not found in signal, manual values will be used as fallback[/dim]")
        else:
            console.print("[green]✓ FREE signals will use MANUAL TP/SL percentages[/green]")
    
    # Manual TP/SL Values (always needed for VIP and as fallback)
    console.print("\n[bold cyan]Manual TP/SL Percentages:[/bold cyan]")
    console.print("[dim]Used for VIP signals and as fallback for FREE signals[/dim]\n")
    
    config.manual_tp_percent = FloatPrompt.ask(
        "[cyan]Take Profit % (without leverage, no max limit)[/cyan]",
        default=10.0
    )
    
    sl_input = FloatPrompt.ask(
        "[cyan]Stop Loss % (without leverage, max 5%)[/cyan]",
        default=2.0
    )
    
    # Enforce 5% max SL HARD CAP
    config.sl_max_percent = 5.0
    if sl_input > config.sl_max_percent:
        console.print(f"[bold red]⚠️  SL HARD CAPPED at {config.sl_max_percent}% (you entered {sl_input}%)[/bold red]")
        config.manual_sl_percent = config.sl_max_percent
    else:
        config.manual_sl_percent = sl_input
    
    # ═══════════════════════════════════════════════════════════════
    # SECTION 5: Price Tolerance
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]═══ PRICE TOLERANCE ═══[/bold yellow]\n")
    console.print("[dim]How much current price can deviate from signal entry price (1%-5%)[/dim]")
    console.print("[dim]If price deviates more than tolerance, trade will be SKIPPED[/dim]\n")
    
    tolerance = FloatPrompt.ask(
        "[cyan]Price tolerance % (1-5)[/cyan]",
        default=3.0
    )
    config.price_tolerance_percent = max(1.0, min(5.0, tolerance)) / 100
    
    # ═══════════════════════════════════════════════════════════════
    # SECTION 6: Multi-Signal Mode - Multiple Trades Same Pair
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]═══ MULTI-SIGNAL MODE ═══[/bold yellow]\n")
    console.print("[dim]The channel is scalping-focused. Multiple signals may come for the same pair:[/dim]")
    console.print("[dim]  • Same direction (multiple LONG signals for BTCUSDT)[/dim]")
    console.print("[dim]  • Opposite direction (LONG then SHORT on same pair)[/dim]")
    console.print("[dim]Configure how to handle these scenarios:[/dim]\n")
    
    config.allow_opposite_direction_same_day = Confirm.ask(
        "[cyan]Allow OPPOSITE direction trades on same pair same day?[/cyan]",
        default=True
    )
    
    if config.allow_opposite_direction_same_day:
        console.print("[green]✓ Will trade BOTH directions if signals come (e.g., LONG then SHORT)[/green]")
    else:
        console.print("[yellow]⚠️  Will only trade FIRST direction signal per pair per day[/yellow]")
    
    console.print("")
    
    # Max same direction trades
    console.print("[dim]For SAME direction signals (e.g., multiple LONG signals on BTCUSDT):[/dim]")
    console.print("[dim]How many times should the bot trade the same pair in same direction per day?[/dim]")
    console.print("[dim]  • 1 = Only first signal (default, safer)[/dim]")
    console.print("[dim]  • 2+ = Follow multiple signals (more aggressive, for VIP scalping)[/dim]")
    console.print("[dim]  • 0 = Unlimited (not recommended)[/dim]\n")
    
    config.max_same_direction_trades_per_day = IntPrompt.ask(
        "[cyan]Max trades per symbol per direction per day[/cyan]",
        default=1
    )
    
    if config.max_same_direction_trades_per_day == 0:
        console.print("[yellow]⚠️  Unlimited trades enabled - be careful![/yellow]")
    elif config.max_same_direction_trades_per_day == 1:
        console.print("[green]✓ Only first signal per pair/direction will be traded[/green]")
    else:
        console.print(f"[green]✓ Will follow up to {config.max_same_direction_trades_per_day} signals per pair/direction[/green]")
    
    # ═══════════════════════════════════════════════════════════════
    # SECTION 7: Dry Run Mode
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold yellow]═══ OPERATION MODE ═══[/bold yellow]\n")
    console.print("[bold red]⚠️  IMPORTANT: Only LIMIT ORDERS are used - NO MARKET ORDERS[/bold red]")
    console.print("[dim]If limit order is not filled within timeout, it will be CANCELLED (not converted to market)[/dim]\n")
    
    config.dry_run = Confirm.ask(
        "[cyan]Enable DRY RUN mode (no real trades)?[/cyan]",
        default=True
    )
    
    if not config.dry_run:
        console.print("\n[bold red]⚠️  WARNING: You are about to enable LIVE TRADING![/bold red]")
        console.print("[red]Real money will be used. Losses are possible.[/red]")
        console.print("[red]Only LIMIT orders will be placed - no market orders.[/red]")
        confirm_live = Confirm.ask(
            "[red]Are you SURE you want to enable LIVE TRADING?[/red]",
            default=False
        )
        if not confirm_live:
            config.dry_run = True
            console.print("[green]✓ Keeping DRY RUN mode enabled for safety[/green]")
    
    # ═══════════════════════════════════════════════════════════════
    # DISPLAY CONFIGURATION SUMMARY
    # ═══════════════════════════════════════════════════════════════
    console.print("\n")
    display_config_summary(config)
    
    # ═══════════════════════════════════════════════════════════════
    # FINAL CONFIRMATION
    # ═══════════════════════════════════════════════════════════════
    confirmed = Confirm.ask(
        "\n[bold green]Continue with these settings?[/bold green]",
        default=True
    )
    
    if not confirmed:
        console.print("[yellow]Restarting configuration...[/yellow]")
        return await interactive_startup()
    
    console.print("\n[bold green]✅ Configuration saved. Starting bot...[/bold green]\n")
    
    return config


def display_config_summary(config: RuntimeConfig):
    """Display configuration in colored table."""
    table = Table(
        title="📋 Configuration Summary",
        border_style="cyan",
        box=box.ROUNDED
    )
    table.add_column("Setting", style="cyan", width=35)
    table.add_column("Value", style="green", width=35)
    
    # Signal Sources
    vip_status = "[green]✅ Enabled[/green]" if config.enable_vip_signals else "[red]❌ Disabled[/red]"
    free_status = "[green]✅ Enabled[/green]" if config.enable_free_signals else "[red]❌ Disabled[/red]"
    table.add_row("VIP Signals", vip_status)
    table.add_row("FREE Signals", free_status)
    table.add_row("", "")  # Spacer
    
    # Position
    table.add_row("Position Size", f"${config.position_size_usdt:.2f} USDT")
    table.add_row("Leverage", f"{config.leverage}×")
    effective_exposure = config.position_size_usdt * config.leverage
    table.add_row("Effective Exposure", f"${effective_exposure:.2f} USDT")
    table.add_row("", "")  # Spacer
    
    # Daily Limits
    max_daily = "Unlimited" if config.max_trades_per_day == 0 else str(config.max_trades_per_day)
    table.add_row("[bold]Max Trades Per Day[/bold]", f"[bold]{max_daily}[/bold]")
    table.add_row("", "")  # Spacer
    
    # TP/SL - Separate for VIP and FREE
    table.add_row("[bold]VIP Signal TP/SL Mode[/bold]", "MANUAL (always)")
    if config.enable_free_signals:
        table.add_row("[bold]FREE Signal TP/SL Mode[/bold]", config.free_tp_sl_mode.value.upper())
    
    # Manual TP/SL values
    table.add_row("Take Profit (no leverage)", f"{config.manual_tp_percent}%")
    table.add_row("Stop Loss (no leverage)", f"{config.manual_sl_percent}%")
    table.add_row("SL Hard Cap", f"[red]{config.sl_max_percent}% MAX[/red]")
    
    tp_with_lev = config.manual_tp_percent * config.leverage
    sl_with_lev = config.manual_sl_percent * config.leverage
    table.add_row(f"TP with {config.leverage}× leverage", f"[yellow]{tp_with_lev}%[/yellow]")
    table.add_row(f"SL with {config.leverage}× leverage", f"[yellow]{sl_with_lev}%[/yellow]")
    
    table.add_row("", "")  # Spacer
    
    # Tolerance
    table.add_row("Price Tolerance", f"{config.price_tolerance_percent*100:.1f}%")
    
    # Multi-Signal Mode
    scalp_status = "[green]✅ Yes[/green]" if config.allow_opposite_direction_same_day else "[yellow]❌ No[/yellow]"
    table.add_row("Opposite Direction Same Day", scalp_status)
    
    max_trades_str = "Unlimited" if config.max_same_direction_trades_per_day == 0 else str(config.max_same_direction_trades_per_day)
    table.add_row("Max Same Direction Trades/Day", max_trades_str)
    
    table.add_row("", "")  # Spacer
    
    # Order Type - Emphasize LIMIT ONLY
    table.add_row("[bold]Order Type[/bold]", "[bold green]LIMIT ONLY[/bold green] (no market orders)")
    
    # Mode
    if config.dry_run:
        mode_display = "[bold green]🟢 DRY RUN (No real trades)[/bold green]"
    else:
        mode_display = "[bold red]🔴 LIVE TRADING (Real money!)[/bold red]"
    table.add_row("Operation Mode", mode_display)
    
    console.print(table)


def display_running_status(config: RuntimeConfig, channel_name: str):
    """Display running status banner."""
    vip_status = "✅" if config.enable_vip_signals else "❌"
    free_status = "✅" if config.enable_free_signals else "❌"
    mode = "🟢 DRY RUN" if config.dry_run else "🔴 LIVE"
    scalp_mode = "✅" if config.allow_opposite_direction_same_day else "❌"
    max_trades = "∞" if config.max_same_direction_trades_per_day == 0 else str(config.max_same_direction_trades_per_day)
    max_daily = "∞" if config.max_trades_per_day == 0 else str(config.max_trades_per_day)
    
    status_panel = Panel(
        f"[bold cyan]🐺 WOLF TRADING BOT v4.1 - RUNNING[/bold cyan]\n\n"
        f"Mode: [{'green' if config.dry_run else 'red'}]{mode}[/{'green' if config.dry_run else 'red'}] | "
        f"VIP: {vip_status} | FREE: {free_status}\n"
        f"Position: ${config.position_size_usdt:.2f} | Leverage: {config.leverage}× | "
        f"[bold]Max Daily: {max_daily}[/bold]\n"
        f"Bi-Directional: {scalp_mode} | Max/Dir: {max_trades} | "
        f"[bold red]LIMIT ORDERS ONLY[/bold red]\n\n"
        f"[dim]Listening to: {channel_name}[/dim]",
        border_style="cyan",
        box=box.DOUBLE
    )
    console.print(status_panel)
