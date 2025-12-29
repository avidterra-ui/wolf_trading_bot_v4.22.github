"""
Message classification for Wolf Trading Bot.
Classifies incoming Telegram messages into signal types.
"""

import re
from typing import Optional, Tuple
from telethon.tl.types import Message

from .models import SignalType
from .utils.logging_setup import get_logger

logger = get_logger(__name__)


# Results/promotional post patterns - if 2+ match, it's a results post
RESULTS_POST_PATTERNS = [
    # Header patterns
    r"TRADE\s*RESULTS?",
    r"PREMIUM\s*TRADE\s*RESULT",
    r"WOLF\s*PREMIUM\s*TRADE\s*RESULT",
    
    # Achievement indicators
    r"Target\s*\d+\s*Achieved",
    r"Take[- ]?Profit\s*Target\s*\d+\s*Achieved",
    r"ALHUMDULILAH",
    r"MASHA\s*ALLAH",
    
    # Profit announcement
    r"\+\s*\d+(\.\d+)?%\s*PROFIT",
    r"with\s*the\s*Profit\s*of",
    r"Profit\s*of\s*:\s*\+?\d+",
    
    # Closing indicators
    r"CLOSE\s*\d+%\s*NOW",
    r"CLOSE\s*NOW",
    r"CLOSED\s*(IN|WITH)\s*PROFIT",
    
    # Promotional
    r"PROOF",
    r"JOIN\s*(VIP|NOW|US|BITUNIX)",
    r"DAILY\s*(PROFIT|RESULT)",
    r"WEEKLY\s*(PROFIT|RESULT)",
]

# Required fields for FREE signal detection (including stop loss)
FREE_SIGNAL_REQUIRED_PATTERNS = [
    r"COIN\s*NAME|#[A-Z0-9]+/USDT?|[A-Z]{2,}USDT",  # Symbol
    r"\b(LONG|SHORT)\b",  # Direction
    r"ENTRY\s*(PRICE)?|ENTRY\s*[:\-]?\s*\d",  # Entry
    r"(?:STOP\s*LOSS|STOPLOSS|SL)\s*[:\-]?\s*[0-9]+",  # Stop loss (required)
]


def is_results_post(text: str) -> bool:
    """
    Detect if message is a results/update post (NOT a new signal).
    Returns True if 2+ patterns match.
    """
    if not text or not isinstance(text, str):
        return False
    
    matches = sum(1 for p in RESULTS_POST_PATTERNS if re.search(p, text, re.IGNORECASE))
    return matches >= 2


def has_required_signal_fields(text: str) -> bool:
    """
    Check if text contains required fields for a free signal.
    Returns True if all required patterns are found.
    """
    if not text or not isinstance(text, str):
        return False
    
    for pattern in FREE_SIGNAL_REQUIRED_PATTERNS:
        if not re.search(pattern, text, re.IGNORECASE):
            return False
    return True


def is_vip_forward(message: Message, vip_title: str = "WOLF OFFICIAL VIP") -> bool:
    """
    Check if message is forwarded from VIP channel.
    
    Args:
        message: Telegram message object
        vip_title: Title of VIP channel to match
        
    Returns:
        True if message is forwarded from VIP channel
    """
    if not message.forward:
        return False
    
    # Check forward_from_chat (channel forwards)
    if hasattr(message.forward, 'chat') and message.forward.chat:
        chat = message.forward.chat
        if hasattr(chat, 'title') and chat.title:
            # Case-insensitive partial match
            if vip_title.lower() in chat.title.lower():
                return True
    
    # Some forwards might have from_id instead
    if hasattr(message.forward, 'from_name') and message.forward.from_name:
        if vip_title.lower() in message.forward.from_name.lower():
            return True
    
    return False


def is_first_vip_signal(message: Message) -> bool:
    """
    DEPRECATED: This function is no longer used in the new classification system.
    VIP signal classification now follows strict 3-rule check:
    1. Forwarded from VIP channel
    2. Forward source contains "WOLF OFFICIAL VIP"
    3. reply_to == None
    
    Text content is NOT used for VIP signal classification.
    """
    # For backward compatibility, just check reply_to (text checking removed)
    if message.reply_to is not None:
        return False
    return True


def classify_message(
    message: Message,
    vip_channel_title: str = "WOLF OFFICIAL VIP",
    enable_vip: bool = True,
    enable_free: bool = True
) -> Tuple[SignalType, str]:
    """
    Classify incoming message type following strict structural rules.
    
    ABSOLUTE STRUCTURAL RULE: Replies are NEVER trading signals.
    Any message where reply_to != None must be ignored.
    
    Args:
        message: Telegram message object
        vip_channel_title: Title to identify VIP forwards
        enable_vip: Whether VIP signals are enabled
        enable_free: Whether FREE signals are enabled
    
    Returns:
        Tuple of (SignalType, reason_string)
    """
    # Rule 1: Check if message is a reply - ALWAYS ignore if true
    if message.reply_to is not None:
        return SignalType.UNKNOWN, "Reply to another message - NEVER a trading signal"
    
    # Rule 2: Check if forwarded from VIP channel
    is_vip = is_vip_forward(message, vip_channel_title)
    
    # VIP Signal Classification (strict 3-rule check)
    if is_vip:
        # Check if VIP signals are enabled
        if not enable_vip:
            return SignalType.UNKNOWN, "VIP signals disabled"
        
        # VIP Signal Rule: forwarded + VIP source + reply_to == None
        # All 3 conditions are met by this point
        return SignalType.VIP_SIGNAL, "Valid VIP signal (forwarded + VIP source + no reply)"
    
    # Not forwarded - check for FREE signal
    else:
        # Check if FREE signals are enabled
        if not enable_free:
            return SignalType.UNKNOWN, "FREE signals disabled"
        
        # Get caption text for validation
        text = message.text or message.message or ""
        if hasattr(message, 'caption') and message.caption:
            text = message.caption
        
        # FREE Signal Rule: NOT forwarded + reply_to == None + required caption fields
        if has_required_signal_fields(text):
            return SignalType.FREE_SIGNAL, "Valid FREE signal (direct + no reply + required fields)"
        
        return SignalType.UNKNOWN, "Missing required FREE signal fields"


def extract_forward_source(message: Message) -> Optional[str]:
    """
    Extract the source channel name from a forwarded message.
    
    Returns:
        Channel name/title or None
    """
    if not message.forward:
        return None
    
    if hasattr(message.forward, 'chat') and message.forward.chat:
        if hasattr(message.forward.chat, 'title'):
            return message.forward.chat.title
    
    if hasattr(message.forward, 'from_name'):
        return message.forward.from_name
    
    return None
