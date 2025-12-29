"""
Real-time feedback system for Wolf Trading Bot.
Provides colored console output for all message processing.
"""

from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich import box

from .models import TradeDirection, OrderDetails, SignalSource


console = Console()


def get_timestamp() -> str:
    """Get formatted timestamp for log output."""
    return datetime.now().strftime('%H:%M:%S')


# ═══════════════════════════════════════════════════════════════
# MESSAGE TYPE FEEDBACK
# ═══════════════════════════════════════════════════════════════

def log_listening(channel_name: str):
    """Log when bot starts listening to channel."""
    console.print(f"\n[{get_timestamp()}] [bold cyan]📡 Listening to: {channel_name}[/bold cyan]\n")


def log_message_received(preview: str = ""):
    """Log when any message is received (for debugging)."""
    if preview:
        preview_short = preview[:50] + "..." if len(preview) > 50 else preview
        console.print(f"[dim][{get_timestamp()}] 📨 Message received: {preview_short}[/dim]")


def log_vip_signal(symbol: str, direction: str, entry_price: Optional[float] = None):
    """Log when VIP signal is detected and being traded."""
    entry_str = f"\nEntry Price: [cyan]{entry_price}[/cyan]" if entry_price else ""
    console.print(Panel(
        f"[bold green]🎯 VIP SIGNAL DETECTED[/bold green]\n\n"
        f"Symbol: [cyan]{symbol}[/cyan]\n"
        f"Direction: [cyan]{direction}[/cyan]"
        f"{entry_str}\n\n"
        f"[bold]→ ENTERING TRADE[/bold]",
        border_style="green",
        box=box.ROUNDED
    ))


def log_vip_reply_ignored():
    """Log when VIP reply/update is ignored."""
    console.print(f"[{get_timestamp()}] [yellow]📝 VIP Reply/Update → IGNORED (not first signal)[/yellow]")


def log_free_signal(symbol: str, direction: str, entry_price: Optional[float] = None):
    """Log when FREE signal is detected and being traded."""
    entry_str = f"\nEntry Price: [cyan]{entry_price}[/cyan]" if entry_price else ""
    console.print(Panel(
        f"[bold blue]📊 FREE SIGNAL DETECTED[/bold blue]\n\n"
        f"Symbol: [cyan]{symbol}[/cyan]\n"
        f"Direction: [cyan]{direction}[/cyan]"
        f"{entry_str}\n\n"
        f"[bold]→ ENTERING TRADE[/bold]",
        border_style="blue",
        box=box.ROUNDED
    ))


def log_promotional_ignored():
    """Log when promotional post is ignored."""
    console.print(f"[{get_timestamp()}] [dim]📢 Promotional post → IGNORED[/dim]")


def log_results_ignored():
    """Log when results/PNL update is ignored."""
    console.print(f"[{get_timestamp()}] [dim]📈 Results/PNL update → IGNORED[/dim]")


def log_unknown_ignored():
    """Log when unknown message type is ignored."""
    console.print(f"[{get_timestamp()}] [dim]❓ Unknown message type → IGNORED[/dim]")


def log_signal_disabled(source: str):
    """Log when signal source is disabled."""
    console.print(f"[{get_timestamp()}] [yellow]⏭️  {source} signal detected but DISABLED in config → SKIPPING[/yellow]")


# ═══════════════════════════════════════════════════════════════
# TRADE EXECUTION FEEDBACK
# ═══════════════════════════════════════════════════════════════

def log_trade_executed(order: OrderDetails, leverage: int = 50):
    """Log successful trade execution."""
    tp_str = ""
    sl_str = ""
    
    if order.tp_price is not None and order.tp_percent is not None:
        tp_with_lev = order.tp_percent * leverage
        tp_str = f"\nTP: [green]{order.tp_price:.6f}[/green] ({order.tp_percent:.1f}% / {tp_with_lev:.0f}% with leverage)"
    
    if order.sl_price is not None and order.sl_percent is not None:
        sl_with_lev = order.sl_percent * leverage
        sl_str = f"\nSL: [red]{order.sl_price:.6f}[/red] ({order.sl_percent:.1f}% / {sl_with_lev:.0f}% with leverage)"
    
    console.print(Panel(
        f"[bold green]✅ TRADE EXECUTED[/bold green]\n\n"
        f"Symbol: [cyan]{order.symbol}[/cyan]\n"
        f"Direction: [cyan]{order.direction.value}[/cyan]\n"
        f"Entry Price: [cyan]{order.entry_price:.6f}[/cyan]\n"
        f"Quantity: [cyan]{order.quantity:.4f}[/cyan]\n"
        f"Leverage: [cyan]{order.leverage}×[/cyan]"
        f"{tp_str}{sl_str}\n\n"
        f"Order ID: [dim]{order.order_id}[/dim]",
        border_style="green",
        box=box.ROUNDED
    ))


def log_trade_skipped(reason: str):
    """Log when trade is skipped."""
    console.print(f"[{get_timestamp()}] [yellow]⏭️  Trade skipped: {reason}[/yellow]")


def log_duplicate_trade(symbol: str, direction: str):
    """Log when duplicate trade is detected."""
    console.print(f"[{get_timestamp()}] [yellow]⏭️  Duplicate trade: {symbol} {direction} already traded today[/yellow]")


def log_tolerance_check(deviation: float, tolerance: float, passed: bool):
    """Log price tolerance check result."""
    status = "[green]✓[/green]" if passed else "[red]✗[/red]"
    console.print(
        f"[{get_timestamp()}] Price tolerance: {deviation*100:.2f}% vs {tolerance*100:.1f}% limit {status}"
    )


def log_tolerance_exceeded(deviation: float, tolerance: float, current_price: float, entry_price: float):
    """Log when price tolerance is exceeded."""
    console.print(Panel(
        f"[bold red]❌ PRICE TOLERANCE EXCEEDED[/bold red]\n\n"
        f"Current Price: [cyan]{current_price:.6f}[/cyan]\n"
        f"Entry Price: [cyan]{entry_price:.6f}[/cyan]\n"
        f"Deviation: [red]{deviation*100:.2f}%[/red]\n"
        f"Tolerance: [yellow]{tolerance*100:.1f}%[/yellow]\n\n"
        f"[yellow]Trade skipped - price moved too far[/yellow]",
        border_style="red",
        box=box.ROUNDED
    ))


def log_dry_run(order: OrderDetails, leverage: int = 50):
    """Log dry run order (not executed)."""
    tp_str = ""
    sl_str = ""
    
    if order.tp_price is not None and order.tp_percent is not None:
        tp_with_lev = order.tp_percent * leverage
        tp_str = f"\nTP: [green]{order.tp_price:.6f}[/green] ({order.tp_percent:.1f}% / {tp_with_lev:.0f}% with leverage)"
    
    if order.sl_price is not None and order.sl_percent is not None:
        sl_with_lev = order.sl_percent * leverage
        sl_str = f"\nSL: [red]{order.sl_price:.6f}[/red] ({order.sl_percent:.1f}% / {sl_with_lev:.0f}% with leverage)"
    
    console.print(Panel(
        f"[bold cyan]🔵 DRY RUN - Order NOT placed[/bold cyan]\n\n"
        f"[dim]Would have executed:[/dim]\n"
        f"Symbol: [cyan]{order.symbol}[/cyan]\n"
        f"Direction: [cyan]{order.direction.value}[/cyan]\n"
        f"Entry Price: [cyan]{order.entry_price:.6f}[/cyan]\n"
        f"Quantity: [cyan]{order.quantity:.4f}[/cyan]\n"
        f"Leverage: [cyan]{order.leverage}×[/cyan]"
        f"{tp_str}{sl_str}",
        border_style="cyan",
        box=box.ROUNDED
    ))


# ═══════════════════════════════════════════════════════════════
# ERROR FEEDBACK
# ═══════════════════════════════════════════════════════════════

def log_error(message: str, details: str = ""):
    """Log error message."""
    detail_str = f"\n[dim]{details}[/dim]" if details else ""
    console.print(f"[{get_timestamp()}] [bold red]❌ ERROR: {message}[/bold red]{detail_str}")


def log_ocr_failed(error: str):
    """Log OCR failure."""
    console.print(f"[{get_timestamp()}] [red]❌ OCR failed: {error} - trade skipped[/red]")


def log_symbol_not_found(symbol: str):
    """Log when symbol is not found on exchange."""
    console.print(f"[{get_timestamp()}] [red]❌ Symbol not found: {symbol} - trade skipped[/red]")


def log_insufficient_balance():
    """Log insufficient balance error."""
    console.print(f"[{get_timestamp()}] [red]❌ Insufficient balance - trade skipped[/red]")


def log_api_error(error: str):
    """Log API error."""
    console.print(f"[{get_timestamp()}] [red]❌ API error: {error}[/red]")


# ═══════════════════════════════════════════════════════════════
# STATUS UPDATES
# ═══════════════════════════════════════════════════════════════

def log_connecting(service: str):
    """Log connection attempt."""
    console.print(f"[{get_timestamp()}] [cyan]🔌 Connecting to {service}...[/cyan]")


def log_connected(service: str):
    """Log successful connection."""
    console.print(f"[{get_timestamp()}] [green]✅ Connected to {service}[/green]")


def log_reconnecting(service: str, attempt: int, max_attempts: int):
    """Log reconnection attempt."""
    console.print(f"[{get_timestamp()}] [yellow]🔄 Reconnecting to {service} (attempt {attempt}/{max_attempts})...[/yellow]")


def log_leverage_set(symbol: str, leverage: int):
    """Log leverage setting."""
    console.print(f"[{get_timestamp()}] [dim]⚙️  Set leverage for {symbol}: {leverage}×[/dim]")


def log_leverage_fallback(symbol: str, requested: int, actual: int):
    """Log when leverage falls back to max available."""
    console.print(f"[{get_timestamp()}] [yellow]⚠️  {symbol}: Requested {requested}× leverage, using max available: {actual}×[/yellow]")


def log_order_placed(order_type: str, symbol: str, side: str, price: float, quantity: float):
    """Log order placement."""
    console.print(
        f"[{get_timestamp()}] [dim]📤 Placing {order_type} order: {side} {quantity:.4f} {symbol} @ {price:.6f}[/dim]"
    )


def log_order_filled(order_id: str, fill_price: float):
    """Log order fill."""
    console.print(f"[{get_timestamp()}] [green]✅ Order {order_id} filled @ {fill_price:.6f}[/green]")


def log_order_cancelled(order_id: str, reason: str = ""):
    """Log order cancellation."""
    reason_str = f" - {reason}" if reason else ""
    console.print(f"[{get_timestamp()}] [yellow]🚫 Order {order_id} cancelled{reason_str}[/yellow]")


def log_image_tp_sl_extracted(take_profits: list, stop_loss: float = None):
    """Log when TP/SL values are extracted from image."""
    tp_str = ", ".join([f"{tp:.6f}" for tp in take_profits]) if take_profits else "None"
    sl_str = f"{stop_loss:.6f}" if stop_loss else "None"
    console.print(f"[{get_timestamp()}] [green]📸 Extracted TP/SL from image: TPs=[{tp_str}], SL={sl_str}[/green]")


def log_same_pair_opposite_direction(symbol: str, new_direction: str, existing_direction: str):
    """Log when trading same pair in opposite direction (scalping mode)."""
    console.print(
        f"[{get_timestamp()}] [cyan]🔄 {symbol}: New {new_direction} signal while {existing_direction} was traded earlier. "
        f"[bold]SCALPING MODE - proceeding with new trade[/bold][/cyan]"
    )


def log_daily_limit_reached(current_count: int, max_count: int):
    """Log when daily trade limit is reached."""
    console.print(Panel(
        f"[bold red]⛔ DAILY TRADE LIMIT REACHED[/bold red]\n\n"
        f"Trades Today: [yellow]{current_count}[/yellow]\n"
        f"Maximum Allowed: [yellow]{max_count}[/yellow]\n\n"
        f"[dim]Trade skipped to protect capital[/dim]",
        border_style="red",
        box=box.ROUNDED
    ))
