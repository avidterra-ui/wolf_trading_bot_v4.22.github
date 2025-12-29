"""
TP/SL calculator with leverage awareness for Wolf Trading Bot v4.1.
Handles TP/SL calculation modes with proper leverage conversion.

Key changes in v4.1:
- VIP signals ALWAYS use manual TP/SL (no TP/SL in VIP images)
- FREE signals can use "from_signal" (parse text/image) or "manual"
- SL hard cap at 5% without leverage
- Removed PNL-based mode
"""

from typing import Optional
from .models import (
    TPSLCalculation, TradeSignal, RuntimeConfig, 
    TPSLMode, TradeDirection, SignalSource
)
from .utils.logging_setup import get_logger

logger = get_logger(__name__)


# SL limits (without leverage)
SL_MIN_PERCENT = 0.5   # Minimum 0.5%
SL_MAX_PERCENT = 5.0   # Maximum 5% - HARD CAP

# TP has no limit but has defaults
TP_DEFAULT_PERCENT = 10.0


def convert_percent_with_leverage(percent_without_leverage: float, leverage: int) -> float:
    """
    Convert percentage from without-leverage to with-leverage.
    
    Example with 50× leverage:
    - 1% without leverage = 50% with leverage
    - 10% without leverage = 500% with leverage
    """
    return percent_without_leverage * leverage


def convert_percent_without_leverage(percent_with_leverage: float, leverage: int) -> float:
    """
    Convert percentage from with-leverage to without-leverage.
    """
    return percent_with_leverage / leverage


def enforce_sl_limits(sl_percent: float, sl_max_percent: float = SL_MAX_PERCENT) -> float:
    """
    Enforce stop loss limits.
    
    Args:
        sl_percent: SL percentage WITHOUT leverage
        sl_max_percent: Maximum allowed SL percentage (default 5%)
        
    Returns:
        Adjusted SL percentage within limits
    """
    if sl_percent < SL_MIN_PERCENT:
        logger.warning(f"SL {sl_percent}% below minimum, adjusting to {SL_MIN_PERCENT}%")
        return SL_MIN_PERCENT
    
    if sl_percent > sl_max_percent:
        logger.warning(f"SL {sl_percent}% exceeds maximum, HARD CAPPING at {sl_max_percent}%")
        return sl_max_percent
    
    return sl_percent


def calculate_tp_sl_prices(
    entry_price: float,
    direction: TradeDirection,
    tp_percent: float,
    sl_percent: float,
    leverage: int = 50,
    sl_max_percent: float = SL_MAX_PERCENT
) -> TPSLCalculation:
    """
    Calculate TP/SL prices from percentages.
    
    All percentages should be WITHOUT leverage.
    
    Args:
        entry_price: Entry price for the trade
        direction: LONG or SHORT
        tp_percent: Take profit % WITHOUT leverage (e.g., 10 for 10%)
        sl_percent: Stop loss % WITHOUT leverage (e.g., 2 for 2%)
        leverage: Leverage multiplier for display purposes
        sl_max_percent: Maximum SL percentage (hard cap)
        
    Returns:
        TPSLCalculation with prices and both leverage/non-leverage percentages
    """
    # Enforce SL limits with hard cap
    sl_percent = enforce_sl_limits(sl_percent, sl_max_percent)
    
    # Convert percentages to price distance
    tp_distance = entry_price * (tp_percent / 100)
    sl_distance = entry_price * (sl_percent / 100)
    
    if direction == TradeDirection.LONG:
        tp_price = entry_price + tp_distance
        sl_price = entry_price - sl_distance
    else:  # SHORT
        tp_price = entry_price - tp_distance
        sl_price = entry_price + sl_distance
    
    return TPSLCalculation(
        tp_price=tp_price,
        sl_price=sl_price,
        tp_percent_without_leverage=tp_percent,
        tp_percent_with_leverage=tp_percent * leverage,
        sl_percent_without_leverage=sl_percent,
        sl_percent_with_leverage=sl_percent * leverage,
    )


def calculate_percent_from_prices(
    entry_price: float,
    target_price: float,
    direction: TradeDirection
) -> float:
    """
    Calculate percentage move from entry to target price.
    
    Returns percentage WITHOUT leverage.
    """
    if direction == TradeDirection.LONG:
        return ((target_price - entry_price) / entry_price) * 100
    else:  # SHORT
        return ((entry_price - target_price) / entry_price) * 100


def get_tp_sl_for_signal(
    signal: TradeSignal,
    config: RuntimeConfig,
    entry_price: float
) -> TPSLCalculation:
    """
    Get TP/SL calculation based on signal source and configured modes.
    
    CRITICAL v4.1 LOGIC:
    - VIP signals: ALWAYS use manual TP/SL (VIP images don't have TP/SL)
    - FREE signals: Use "from_signal" mode or "manual" based on config
    - SL is HARD CAPPED at 5% (without leverage)
    
    Args:
        signal: The trading signal
        config: Runtime configuration
        entry_price: Actual entry price used
        
    Returns:
        TPSLCalculation with TP/SL prices and percentages
    """
    leverage = config.leverage
    sl_max = config.sl_max_percent  # Hard cap from config (default 5%)
    
    # Determine which mode to use based on signal source
    if signal.source == SignalSource.VIP:
        # VIP signals ALWAYS use manual mode (no TP/SL in VIP images)
        tp_percent = config.manual_tp_percent
        sl_percent = config.manual_sl_percent
        
        logger.debug(f"VIP signal - using MANUAL TP/SL: TP={tp_percent}%, SL={sl_percent}%")
        
    elif signal.source == SignalSource.FREE:
        # FREE signals - check the mode
        if config.free_tp_sl_mode == TPSLMode.FROM_SIGNAL:
            # Try to use TP/SL from the signal text/image
            tp_percent = None
            sl_percent = None
            
            # Extract TP from signal if available
            if signal.take_profits:
                tp_price = signal.take_profits[0]  # Use first TP target
                tp_percent = abs(calculate_percent_from_prices(
                    entry_price, tp_price, signal.direction
                ))
                logger.debug(f"FREE signal - extracted TP from signal: {tp_percent:.2f}%")
            
            # Extract SL from signal if available
            if signal.stop_loss:
                sl_percent = abs(calculate_percent_from_prices(
                    entry_price, signal.stop_loss, signal.direction
                ))
                logger.debug(f"FREE signal - extracted SL from signal: {sl_percent:.2f}%")
                
                # CRITICAL: Enforce SL hard cap even on signal-extracted values
                if sl_percent > sl_max:
                    logger.warning(f"Signal SL {sl_percent:.2f}% exceeds {sl_max}% cap - adjusting")
                    sl_percent = sl_max
            
            # Fall back to manual values if not found in signal
            if tp_percent is None:
                tp_percent = config.manual_tp_percent
                logger.debug(f"FREE signal - no TP in signal, using manual fallback: {tp_percent}%")
            
            if sl_percent is None:
                sl_percent = config.manual_sl_percent
                logger.debug(f"FREE signal - no SL in signal, using manual fallback: {sl_percent}%")
        
        else:
            # FREE signals with manual mode
            tp_percent = config.manual_tp_percent
            sl_percent = config.manual_sl_percent
            
            logger.debug(f"FREE signal - using MANUAL TP/SL: TP={tp_percent}%, SL={sl_percent}%")
    
    else:
        # Unknown source - default to manual
        tp_percent = config.manual_tp_percent
        sl_percent = config.manual_sl_percent
        logger.warning(f"Unknown signal source - using manual TP/SL")
    
    return calculate_tp_sl_prices(
        entry_price=entry_price,
        direction=signal.direction,
        tp_percent=tp_percent,
        sl_percent=sl_percent,
        leverage=leverage,
        sl_max_percent=sl_max
    )


def format_tp_sl_display(calc: TPSLCalculation) -> str:
    """
    Format TP/SL calculation for display.
    
    Returns:
        Formatted string showing TP/SL with and without leverage
    """
    return (
        f"TP: {calc.tp_price:.6f} "
        f"({calc.tp_percent_without_leverage:.1f}% / {calc.tp_percent_with_leverage:.0f}% with leverage)\n"
        f"SL: {calc.sl_price:.6f} "
        f"({calc.sl_percent_without_leverage:.1f}% / {calc.sl_percent_with_leverage:.0f}% with leverage)"
    )
