"""
Data models and type definitions for Wolf Trading Bot.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List
from datetime import datetime


class SignalType(Enum):
    """Classification of incoming Telegram messages."""
    VIP_SIGNAL = auto()      # First forwarded post from VIP (tradeable)
    VIP_REPLY = auto()       # Reply/update to VIP signal (IGNORE)
    FREE_SIGNAL = auto()     # Direct text signal (tradeable)
    PROMOTIONAL = auto()     # Promo/results post (IGNORE)
    UNKNOWN = auto()         # Cannot classify (IGNORE)


class SignalSource(Enum):
    """Source of the trading signal."""
    VIP = "VIP"
    FREE = "FREE"


class TradeDirection(Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class TPSLMode(Enum):
    """TP/SL calculation mode."""
    MANUAL = "manual"
    FROM_SIGNAL = "from_signal"


class OrderStatus(Enum):
    """Order execution status."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class TradeSignal:
    """Parsed trading signal data."""
    source: SignalSource
    symbol: str
    direction: TradeDirection
    entry_price: Optional[float] = None
    entry_price_low: Optional[float] = None
    entry_price_high: Optional[float] = None
    take_profits: List[float] = field(default_factory=list)
    stop_loss: Optional[float] = None
    leverage: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    raw_text: str = ""
    message_id: Optional[int] = None
    
    @property
    def entry_reference(self) -> Optional[float]:
        """Get reference entry price (average if range, else single price)."""
        if self.entry_price is not None:
            return self.entry_price
        if self.entry_price_low is not None and self.entry_price_high is not None:
            return (self.entry_price_low + self.entry_price_high) / 2
        return None
    
    @property
    def nearest_entry_boundary(self) -> Optional[float]:
        """Get nearest entry boundary to current price for tolerance calculation."""
        if self.entry_price is not None:
            return self.entry_price
        return self.entry_price_high  # Use upper boundary for limit orders


@dataclass
class ImageAnalysisResult:
    """Result from OCR analysis of VIP signal image."""
    is_valid: bool
    symbol: Optional[str] = None
    direction: Optional[TradeDirection] = None
    entry_price: Optional[float] = None
    last_price: Optional[float] = None
    leverage: Optional[int] = None
    profit_percent: Optional[float] = None
    platform: str = "unknown"
    error: Optional[str] = None
    raw_ocr_text: str = ""


@dataclass
class TPSLCalculation:
    """TP/SL price calculation result."""
    tp_price: float
    sl_price: float
    tp_percent_without_leverage: float
    tp_percent_with_leverage: float
    sl_percent_without_leverage: float
    sl_percent_with_leverage: float


@dataclass
class OrderDetails:
    """Order execution details."""
    symbol: str
    direction: TradeDirection
    entry_price: float
    quantity: float
    leverage: int
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    tp_percent: Optional[float] = None
    sl_percent: Optional[float] = None
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RuntimeConfig:
    """Runtime configuration from interactive startup."""
    enable_vip_signals: bool = True
    enable_free_signals: bool = True
    position_size_usdt: float = 1.0
    leverage: int = 50
    
    # TP/SL modes - separate for VIP and FREE signals
    # VIP: Always uses manual (no TP/SL in VIP signal images)
    # FREE: Can use "from_signal" or "manual"
    free_tp_sl_mode: TPSLMode = TPSLMode.FROM_SIGNAL
    vip_tp_sl_mode: TPSLMode = TPSLMode.MANUAL  # Always manual for VIP
    
    # Manual TP/SL percentages (without leverage)
    manual_tp_percent: float = 10.0
    manual_sl_percent: float = 2.0
    
    # SL hard cap: 5% without leverage (250% at 50x)
    sl_max_percent: float = 5.0
    
    price_tolerance_percent: float = 0.03
    dry_run: bool = True
    
    # Scalping mode: Allow multiple trades on same pair with different directions
    allow_opposite_direction_same_day: bool = False
    
    # Maximum number of trades per symbol per day (0 = unlimited)
    # This applies to SAME direction - e.g., max 2 LONG signals on BTCUSDT/day
    max_same_direction_trades_per_day: int = 1
    
    # Maximum total trades per day across all symbols
    max_trades_per_day: int = 5
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'enable_vip_signals': self.enable_vip_signals,
            'enable_free_signals': self.enable_free_signals,
            'position_size_usdt': self.position_size_usdt,
            'leverage': self.leverage,
            'free_tp_sl_mode': self.free_tp_sl_mode.value,
            'vip_tp_sl_mode': self.vip_tp_sl_mode.value,
            'manual_tp_percent': self.manual_tp_percent,
            'manual_sl_percent': self.manual_sl_percent,
            'sl_max_percent': self.sl_max_percent,
            'price_tolerance_percent': self.price_tolerance_percent,
            'dry_run': self.dry_run,
            'allow_opposite_direction_same_day': self.allow_opposite_direction_same_day,
            'max_same_direction_trades_per_day': self.max_same_direction_trades_per_day,
            'max_trades_per_day': self.max_trades_per_day,
        }


@dataclass
class TelegramConfig:
    """Telegram connection configuration."""
    api_id: int
    api_hash: str
    session_name: str = "wolf_trading_bot"
    public_channel_username: str = "thewolfofcrypto1"
    public_channel_title: str = "THE WOLF (CRYPTO)"
    vip_channel_title: str = "WOLF OFFICIAL VIP"
    retry_delay_seconds: int = 5
    max_retries: int = 10


@dataclass
class BingXConfig:
    """BingX API configuration."""
    api_key: str
    api_secret: str
    base_url: str = "https://open-api.bingx.com"
    default_leverage: int = 50
    fallback_to_max_leverage: bool = True
