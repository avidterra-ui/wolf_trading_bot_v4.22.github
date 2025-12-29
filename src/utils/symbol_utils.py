"""
Symbol normalization utilities for Wolf Trading Bot.
Ensures consistent BingX USDT-M Swap V2 symbol format across all parsers.

CRITICAL BingX USDT-M Swap V2 Requirements:
- Symbols MUST use a dash separator
- Format: BASE-USDT  
- Use the EXACT `symbol` field returned by the API

VALID:  BTC-USDT, ETH-USDT, TRADOOR-USDT
INVALID: BTCUSDT, BTC/USDT
"""

import re
from typing import Optional

try:
    from .logging_setup import get_logger
except ImportError:
    # Fallback for direct execution
    import logging
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)


def normalize_symbol(raw_symbol: str) -> str:
    """
    Normalize symbol to BingX USDT-M Swap V2 format: BASE-USDT (with dash).
    
    CRITICAL: BingX Swap V2 USDT-M Perpetual Futures REQUIRES dash separator.
    
    VALID format:   BTC-USDT, ETH-USDT, TRADOOR-USDT
    INVALID format: BTCUSDT, BTC/USDT
    
    Examples:
        "THE(USDT)" -> "THE-USDT"
        "#BEAT/USDT" -> "BEAT-USDT"
        "1000LUNC (USDT)" -> "1000LUNC-USDT"
        "ICNTUSDT" -> "ICNT-USDT"
        "$ICNT" -> "ICNT-USDT"
        "#TRADOOR/USDT°" -> "TRADOOR-USDT"
        "BTC-USDT" -> "BTC-USDT" (already correct)
    
    Args:
        raw_symbol: Raw symbol string from any source (text, OCR, etc.)
        
    Returns:
        Normalized symbol in BASE-USDT format, or empty string if invalid
    """
    if not raw_symbol:
        logger.debug("Empty symbol provided")
        return ''
    
    # Common symbol typo corrections
    typo_corrections = {
        'STROJ': 'STORJ',  # Common typo: O instead of R
        # Add more corrections as needed
    }
    
    # Remove special characters but keep dashes temporarily
    cleaned = re.sub(r'[$#\(\)/\s°]', '', raw_symbol.upper())
    
    # Remove any existing dash for normalization
    cleaned = cleaned.replace('-', '')
    
    # Remove duplicate USDT and trailing USDT
    cleaned = re.sub(r'(USDT)+$', '', cleaned)
    
    # Apply typo corrections
    if cleaned in typo_corrections:
        corrected = typo_corrections[cleaned]
        logger.debug(f"Applied typo correction: '{cleaned}' -> '{corrected}'")
        cleaned = corrected
    
    # Construct final format: BASE-USDT
    if not cleaned:
        logger.debug(f"Symbol '{raw_symbol}' resulted in empty cleaned string")
        return ''
    
    normalized = f"{cleaned}-USDT"
    logger.debug(f"Normalized '{raw_symbol}' -> '{normalized}'")
    return normalized


def validate_symbol_format(symbol: str) -> bool:
    """
    Validate that a symbol follows the BingX USDT-M Swap V2 format.
    
    Args:
        symbol: Symbol to validate
        
    Returns:
        True if format is correct (BASE-USDT), False otherwise
    """
    if not symbol:
        return False
    
    # Check for exact BASE-USDT pattern
    pattern = r'^[A-Z0-9]+-USDT$'
    is_valid = bool(re.match(pattern, symbol.upper()))
    
    if not is_valid:
        logger.debug(f"Symbol '{symbol}' failed format validation")
    
    return is_valid


def extract_symbol_from_various_formats(text: str) -> Optional[str]:
    """
    Extract symbol from various text formats and normalize it.
    
    This function handles multiple symbol formats that might appear in:
    - Telegram captions
    - OCR text from images
    - Manual input
    
    Supported formats:
    - #SYMBOL/USDT
    - SYMBOL(USDT)
    - SYMBOLUSDT
    - $SYMBOL
    - SYMBOL-USDT (already normalized)
    
    Args:
        text: Text containing symbol information
        
    Returns:
        Normalized symbol in BASE-USDT format, or None if not found
    """
    # Symbol extraction patterns (ordered by priority)
    patterns = [
        # "COIN NAME: 1000LUNC(USDT)" or "COIN NAME: THE (USDT)"
        r"COIN\s*NAME\s*[:\-]?\s*([A-Za-z0-9#_]+)\s*\(?([A-Za-z]*)\)?",
        # "#BEAT/USDT" or "#ICNT/USDT" or "STORJ/USDT" (with or without #)
        r"#?([A-Z0-9]+)\s*[/]\s*USDT",
        r"#([A-Z0-9]+)\s*[\(/]?\s*(USDT?)\s*\)?",
        # "BEATUSDT" or "ICNTUSDT"
        r"\b([A-Z0-9]{2,})(USDT)\b",
        # "$ICNT" style
        r"\$([A-Z0-9]+)",
        # Already normalized "BTC-USDT"
        r"\b([A-Z0-9]+)-USDT\b",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Extract the base symbol part
            if match.lastindex >= 2:
                # Pattern with quote asset (e.g., "LUNC(USDT)")
                symbol = match.group(1)
            else:
                symbol = match.group(1)
            
            normalized = normalize_symbol(symbol)
            if normalized and validate_symbol_format(normalized):
                logger.debug(f"Extracted and normalized symbol: '{normalized}' from pattern: {pattern}")
                return normalized
    
    logger.debug("No valid symbol found in text")
    return None


# Export the main function for backward compatibility
__all__ = [
    'normalize_symbol',
    'validate_symbol_format', 
    'extract_symbol_from_various_formats'
]
