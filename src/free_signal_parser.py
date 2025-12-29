"""
FREE signal parser for Wolf Trading Bot.
Parses direct text signals from THE WOLF (CRYPTO) channel.
"""

import re
from typing import Optional, List, Tuple
from datetime import datetime

from .models import TradeSignal, TradeDirection, SignalSource
from .utils.logging_setup import get_logger
from .utils.symbol_utils import extract_symbol_from_various_formats, normalize_symbol

logger = get_logger(__name__)


# Symbol extraction patterns
SYMBOL_PATTERNS = [
    # "COIN NAME: 1000LUNC(USDT)" or "COIN NAME: THE (USDT)"
    r"COIN\s*NAME\s*[:\-]?\s*([A-Za-z0-9#_]+)\s*\(?([A-Za-z]*)\)?",
    # "#BEAT/USDT" or "#ICNT/USDT"
    r"#([A-Z0-9]+)\s*[\(/]?\s*(USDT?)\s*\)?",
    # "BEATUSDT" or "ICNTUSDT"
    r"\b([A-Z0-9]{2,})(USDT)\b",
    # "$ICNT" style
    r"\$([A-Z0-9]+)",
]

# Direction patterns
DIRECTION_PATTERNS = [
    r"TRADE\s*TYPE\s*[:\-]?\s*(LONG|SHORT)",
    r"DIRECTION\s*[:\-]?\s*(LONG|SHORT)",
    r"\b(LONG)\s*[📈🟢]",
    r"\b(SHORT)\s*[📉🔴]",
    r"🔼\s*TRADE\s*TYPE\s*[:\-]?\s*(LONG)",
    r"🔽\s*TRADE\s*TYPE\s*[:\-]?\s*(SHORT)",
    r"\b(LONG)\b",
    r"\b(SHORT)\b",
]

# Entry price patterns (supports ranges like "0.04040-0.03950")
ENTRY_PATTERNS = [
    # "ENTRY PRICE (0.04040-0.03950)"
    r"ENTRY\s*PRICE\s*\(?\s*([0-9]*\.?[0-9]+)\s*[-–—]\s*([0-9]*\.?[0-9]+)\s*\)?",
    # "ENTRY: 0.04040-0.03950"
    r"ENTRY\s*[:\-]?\s*([0-9]*\.?[0-9]+)\s*[-–—]\s*([0-9]*\.?[0-9]+)",
    # "ENTRY ZONE: 0.04040-0.03950"
    r"ENTRY\s*ZONE\s*[:\-]?\s*([0-9]*\.?[0-9]+)\s*[-–—]\s*([0-9]*\.?[0-9]+)",
    # Single entry price
    r"ENTRY\s*(?:PRICE)?\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
]

# Take profit patterns
TP_PATTERNS = [
    # "1️⃣ 0.04150"
    r"(?:[1-6]️⃣|[1-6]⃣)\s*([0-9]*\.?[0-9]+)",
    # "TP1: 0.04150" or "TP 1: 0.04150"
    r"TP\s*[1-6]\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
    # "TAKE PROFIT 1: 0.04150"
    r"TAKE[\s\-]?PROFIT\s*[1-6]?\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
    # "TARGET 1: 0.04150"
    r"TARGET\s*[1-6]\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
]

# Stop loss patterns
SL_PATTERNS = [
    # "STOP LOSS: 0.03860"
    r"(?:STOP\s*LOSS|STOPLOSS|SL)\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
    # "SL: HOLD" (no SL set)
    r"(?:STOP\s*LOSS|STOPLOSS|SL)\s*[:\-]?\s*(HOLD)",
]

# Leverage patterns
LEVERAGE_PATTERNS = [
    r"LEVERAGE\s*[:\-]?\s*(\d+)\s*[xX×]?",
    r"(\d+)\s*[xX×]\s*LEVERAGE",
    r"\b(\d+)[xX×]\b",
]


def extract_symbol(text: str) -> Optional[str]:
    """Extract trading symbol from message text using shared utility."""
    return extract_symbol_from_various_formats(text)


def extract_direction(text: str) -> Optional[TradeDirection]:
    """Extract trade direction from message text."""
    for pattern in DIRECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            direction_str = match.group(1).upper()
            logger.debug(f"Extracted direction: {direction_str}")
            return TradeDirection.LONG if direction_str == "LONG" else TradeDirection.SHORT
    
    return None


def extract_entry_price(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract entry price(s) from message text.
    
    Returns:
        Tuple of (entry_low, entry_high) or (single_price, None)
    """
    for pattern in ENTRY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                if match.lastindex >= 2:
                    # Range pattern
                    price1 = float(match.group(1))
                    price2 = float(match.group(2))
                    entry_low = min(price1, price2)
                    entry_high = max(price1, price2)
                    logger.debug(f"Extracted entry range: {entry_low} - {entry_high}")
                    return entry_low, entry_high
                else:
                    # Single price
                    price = float(match.group(1))
                    logger.debug(f"Extracted single entry: {price}")
                    return price, None
            except (ValueError, IndexError):
                continue
    
    return None, None


def extract_take_profits(text: str) -> List[float]:
    """Extract take profit levels from message text."""
    tps = []
    
    for pattern in TP_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                tp = float(match)
                if tp not in tps:  # Avoid duplicates
                    tps.append(tp)
            except ValueError:
                continue
    
    # Sort TPs (usually from closest to farthest)
    tps.sort()
    logger.debug(f"Extracted TPs: {tps}")
    return tps


def extract_stop_loss(text: str) -> Optional[float]:
    """Extract stop loss from message text."""
    for pattern in SL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            sl_value = match.group(1)
            if sl_value.upper() == "HOLD":
                logger.debug("SL is HOLD - no stop loss set")
                return None
            try:
                sl = float(sl_value)
                logger.debug(f"Extracted SL: {sl}")
                return sl
            except ValueError:
                continue
    
    return None


def extract_leverage(text: str) -> Optional[int]:
    """Extract leverage from message text."""
    for pattern in LEVERAGE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                leverage = int(match.group(1))
                if 1 <= leverage <= 200:  # Reasonable leverage range
                    logger.debug(f"Extracted leverage: {leverage}x")
                    return leverage
            except ValueError:
                continue
    
    return None


def parse_free_signal(text: str, message_id: Optional[int] = None) -> Optional[TradeSignal]:
    """
    Parse a FREE signal from text.
    
    Args:
        text: Raw message text
        message_id: Optional Telegram message ID
        
    Returns:
        TradeSignal if successfully parsed, None otherwise
    """
    if not text:
        return None
    
    # Extract required fields
    symbol = extract_symbol(text)
    direction = extract_direction(text)
    
    if not symbol or not direction:
        logger.debug(f"Missing required fields - symbol: {symbol}, direction: {direction}")
        return None
    
    # Extract entry price
    entry_low, entry_high = extract_entry_price(text)
    
    if entry_low is None:
        logger.debug("No entry price found")
        return None
    
    # Extract optional fields
    take_profits = extract_take_profits(text)
    stop_loss = extract_stop_loss(text)
    leverage = extract_leverage(text)
    
    # Create signal
    signal = TradeSignal(
        source=SignalSource.FREE,
        symbol=symbol,
        direction=direction,
        entry_price=entry_low if entry_high is None else None,
        entry_price_low=entry_low if entry_high is not None else None,
        entry_price_high=entry_high,
        take_profits=take_profits,
        stop_loss=stop_loss,
        leverage=leverage,
        timestamp=datetime.now(),
        raw_text=text,
        message_id=message_id,
    )
    
    logger.info(f"Parsed FREE signal: {symbol} {direction.value}")
    return signal


# Example signal for testing
EXAMPLE_FREE_SIGNAL = """
👍THE WOLF SCALPER👍

✔️COIN NAME: 1000LUNC(USDT)

LEVERAGE: 75x

🔼TRADE TYPE: LONG 📈

✔️ENTRY PRICE (0.04040-0.03950)

☄️TAKE-PROFITS

1️⃣ 0.04150
2️⃣ 0.04250
3️⃣ 0.04400

STOP LOSS: 0.03860
"""
