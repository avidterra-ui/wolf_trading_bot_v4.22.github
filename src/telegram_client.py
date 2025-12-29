"""
Secure Telegram client for Wolf Trading Bot v4.1.
Monitors public channel for trading signals with minimal permissions.

CRITICAL v4.1 Signal Source Identification:
- VIP Signals: Direction extracted from IMAGE via OCR (Bitunix card)
- FREE Signals: ALL data extracted from CAPTION text via Regex
- Images in FREE signals are ONLY used to supplement TP/SL if not in text
"""

import asyncio
from typing import Optional, Callable, Awaitable, List
from datetime import datetime

from telethon import TelegramClient, events
from telethon.tl.types import Message, Channel, InputPeerChannel
from telethon.errors import FloodWaitError, ChannelPrivateError

from .models import TelegramConfig, SignalType, TradeSignal, RuntimeConfig
from .message_classifier import classify_message, extract_forward_source
from .free_signal_parser import parse_free_signal
from .image_analyzer import analyze_vip_signal_image, analyze_free_signal_image
from .utils.logging_setup import get_logger
from . import feedback

logger = get_logger(__name__)


class TelegramMonitor:
    """
    Secure Telegram client for monitoring trading channels.
    
    Security measures:
    1. Only reads from permitted channel(s)
    2. Does NOT access user's private messages
    3. Does NOT access other channels/groups
    4. No message sending capability (read-only)
    """
    
    def __init__(
        self,
        config: TelegramConfig,
        runtime_config: RuntimeConfig,
        tesseract_cmd: Optional[str] = None
    ):
        """
        Initialize Telegram monitor.
        
        Args:
            config: Telegram connection configuration
            runtime_config: Runtime settings (VIP/FREE enabled, etc.)
            tesseract_cmd: Path to tesseract executable (for Windows)
        """
        self.config = config
        self.runtime_config = runtime_config
        self.tesseract_cmd = tesseract_cmd
        
        self.client: Optional[TelegramClient] = None
        self.channel_entity: Optional[Channel] = None
        self._signal_handlers: List[Callable[[TradeSignal], Awaitable[None]]] = []
        self._running = False
        
        # Track processed messages to avoid duplicates
        self._processed_messages: set = set()
    
    def add_signal_handler(self, handler: Callable[[TradeSignal], Awaitable[None]]):
        """Add a handler to be called when a valid signal is received."""
        self._signal_handlers.append(handler)
    
    async def _notify_handlers(self, signal: TradeSignal):
        """Notify all registered handlers of a new signal."""
        for handler in self._signal_handlers:
            try:
                await handler(signal)
            except Exception as e:
                logger.exception(f"Signal handler error: {e}")
    
    async def connect(self) -> bool:
        """
        Connect to Telegram and verify channel access.
        
        Returns:
            True if connected successfully
        """
        feedback.log_connecting("Telegram")
        
        try:
            self.client = TelegramClient(
                self.config.session_name,
                self.config.api_id,
                self.config.api_hash,
            )
            
            await self.client.start()
            
            if not await self.client.is_user_authorized():
                logger.error("Telegram user not authorized. Please run auth flow first.")
                return False
            
            # Resolve channel
            try:
                self.channel_entity = await self.client.get_entity(
                    self.config.public_channel_username
                )
                logger.info(f"Connected to channel: {self.channel_entity.title}")
            except Exception as e:
                # Try by title
                logger.warning(f"Could not resolve by username, trying title: {e}")
                dialogs = await self.client.get_dialogs()
                for dialog in dialogs:
                    if hasattr(dialog.entity, 'title'):
                        if self.config.public_channel_title.lower() in dialog.entity.title.lower():
                            self.channel_entity = dialog.entity
                            break
                
                if not self.channel_entity:
                    logger.error(f"Could not find channel: {self.config.public_channel_username}")
                    return False
            
            feedback.log_connected("Telegram")
            return True
            
        except FloodWaitError as e:
            logger.error(f"Flood wait: {e.seconds} seconds")
            return False
        except Exception as e:
            logger.exception(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Telegram."""
        self._running = False
        if self.client:
            await self.client.disconnect()
    
    async def _process_message(self, message: Message):
        """
        Process incoming message and extract signal if valid.
        """
        # Skip if already processed
        if message.id in self._processed_messages:
            return
        self._processed_messages.add(message.id)
        
        # Limit processed messages cache size
        if len(self._processed_messages) > 1000:
            self._processed_messages = set(list(self._processed_messages)[-500:])
        
        # Get message text for preview
        text = message.text or message.message or ""
        if hasattr(message, 'caption') and message.caption:
            text = message.caption
        
        # Log message received
        feedback.log_message_received(text[:50] if text else "[media]")
        
        # Classify message
        signal_type, reason = classify_message(
            message,
            vip_channel_title=self.config.vip_channel_title,
            enable_vip=self.runtime_config.enable_vip_signals,
            enable_free=self.runtime_config.enable_free_signals,
        )
        
        logger.debug(f"Message {message.id} classified as {signal_type.name}: {reason}")
        
        # Handle based on type
        if signal_type == SignalType.VIP_SIGNAL:
            await self._process_vip_signal(message)
            
        elif signal_type == SignalType.FREE_SIGNAL:
            await self._process_free_signal(message, text)
            
        elif signal_type == SignalType.VIP_REPLY:
            feedback.log_vip_reply_ignored()
            
        elif signal_type == SignalType.PROMOTIONAL:
            feedback.log_promotional_ignored()
            
        else:
            feedback.log_unknown_ignored()
    
    async def _process_vip_signal(self, message: Message):
        """
        Process a VIP signal (forwarded with image).
        
        CRITICAL v4.1: VIP signal DIRECTION must be extracted from the IMAGE
        via OCR (the Bitunix card shows 'Long' or 'Short' badge).
        The caption only contains the symbol, not the direction.
        """
        if not self.runtime_config.enable_vip_signals:
            feedback.log_signal_disabled("VIP")
            return
        
        if not message.photo:
            logger.warning("VIP signal without photo")
            return
        
        try:
            # Download photo
            photo_bytes = await self.client.download_media(message.photo, bytes)
            
            if not photo_bytes:
                logger.error("Failed to download photo")
                return
            
            # Get caption
            caption = message.text or message.message or ""
            if hasattr(message, 'caption') and message.caption:
                caption = message.caption
            
            # Analyze image
            from .image_analyzer import analyze_vip_signal_image
            result = await analyze_vip_signal_image(
                photo_bytes,
                caption,
                self.tesseract_cmd
            )
            
            if not result.is_valid:
                feedback.log_ocr_failed(result.error or "Unknown error")
                return
            
            # Create signal
            from .models import SignalSource
            signal = TradeSignal(
                source=SignalSource.VIP,
                symbol=result.symbol,
                direction=result.direction,
                entry_price=result.entry_price,
                leverage=result.leverage,
                timestamp=datetime.now(),
                raw_text=caption,
                message_id=message.id,
            )
            
            feedback.log_vip_signal(signal.symbol, signal.direction.value, signal.entry_price)
            
            # Notify handlers
            await self._notify_handlers(signal)
            
        except Exception as e:
            logger.exception(f"VIP signal processing failed: {e}")
            feedback.log_error("VIP signal processing failed", str(e))
    
    async def _process_free_signal(self, message: Message, text: str):
        """
        Process a FREE signal (direct text post or with attached image).
        
        CRITICAL v4.1: FREE signal data is extracted from CAPTION TEXT via Regex.
        - Symbol, Direction, Entry: All from caption text
        - TP/SL: Primarily from caption, supplemented by image OCR if available
        - DO NOT ignore signals just because they have images
        """
        if not self.runtime_config.enable_free_signals:
            feedback.log_signal_disabled("FREE")
            return
        
        try:
            # First, parse the text signal
            signal = parse_free_signal(text, message.id)
            
            if not signal:
                logger.warning("Failed to parse free signal from text")
                return
            
            # If the message has an attached photo, try to extract TP/SL from it
            if message.photo and (not signal.take_profits or not signal.stop_loss):
                logger.info("FREE signal has attached image - attempting to extract TP/SL")
                try:
                    photo_bytes = await self.client.download_media(message.photo, bytes)
                    
                    if photo_bytes:
                        from .image_analyzer import analyze_free_signal_image
                        image_result = await analyze_free_signal_image(
                            photo_bytes,
                            self.tesseract_cmd
                        )
                        
                        if image_result.is_valid:
                            # Merge image TP/SL into signal if not already set
                            if not signal.take_profits and image_result.take_profits:
                                signal.take_profits = image_result.take_profits
                                logger.info(f"Extracted TPs from image: {signal.take_profits}")
                            
                            if not signal.stop_loss and image_result.stop_loss:
                                signal.stop_loss = image_result.stop_loss
                                logger.info(f"Extracted SL from image: {signal.stop_loss}")
                            
                            # Also merge other data if available and not already set
                            if not signal.leverage and image_result.leverage:
                                signal.leverage = image_result.leverage
                                logger.info(f"Extracted leverage from image: {signal.leverage}x")
                            
                            feedback.log_image_tp_sl_extracted(
                                signal.take_profits,
                                signal.stop_loss
                            )
                        else:
                            logger.warning(f"Image OCR failed: {image_result.error}")
                except Exception as img_err:
                    logger.warning(f"Image extraction failed: {img_err}")
                    # Continue with text-only signal
            
            feedback.log_free_signal(signal.symbol, signal.direction.value, signal.entry_reference)
            
            # Notify handlers
            await self._notify_handlers(signal)
            
        except Exception as e:
            logger.exception(f"FREE signal processing failed: {e}")
            feedback.log_error("FREE signal processing failed", str(e))
    
    async def start_monitoring(self):
        """
        Start monitoring the channel for signals.
        This is the main loop that listens for new messages.
        """
        if not self.client or not self.channel_entity:
            logger.error("Not connected. Call connect() first.")
            return
        
        self._running = True
        channel_title = getattr(self.channel_entity, 'title', 'Unknown')
        
        feedback.log_listening(channel_title)
        
        # Register event handler
        @self.client.on(events.NewMessage(chats=self.channel_entity))
        async def handler(event):
            if not self._running:
                return
            try:
                await self._process_message(event.message)
            except Exception as e:
                logger.exception(f"Message processing error: {e}")
        
        # Keep running until stopped
        while self._running:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
    
    async def fetch_recent_messages(self, limit: int = 10) -> List[Message]:
        """
        Fetch recent messages from the channel.
        Useful for testing or catching up on missed signals.
        """
        if not self.client or not self.channel_entity:
            return []
        
        messages = []
        async for message in self.client.iter_messages(self.channel_entity, limit=limit):
            messages.append(message)
        
        return messages
    
    def get_permissions_summary(self) -> str:
        """Return human-readable permissions summary."""
        return """
╔══════════════════════════════════════════════════════════════╗
║                    TELEGRAM PERMISSIONS                       ║
╠══════════════════════════════════════════════════════════════╣
║ ✅ READ messages from: THE WOLF (CRYPTO)®                    ║
║ ❌ CANNOT read your private messages                         ║
║ ❌ CANNOT read other channels/groups                         ║
║ ❌ CANNOT send messages                                      ║
║ ❌ CANNOT access contacts                                    ║
╚══════════════════════════════════════════════════════════════╝
        """


async def create_telegram_session(api_id: int, api_hash: str, session_name: str = "wolf_trading_bot"):
    """
    Create a new Telegram session (first-time setup).
    
    This will prompt for phone number and verification code.
    """
    print("\n" + "="*60)
    print("TELEGRAM AUTHENTICATION")
    print("="*60)
    print("\nThis will create a new session for the trading bot.")
    print("You will need to enter your phone number and verification code.\n")
    
    client = TelegramClient(session_name, api_id, api_hash)
    
    await client.start()
    
    if await client.is_user_authorized():
        print("\n✅ Session created successfully!")
        me = await client.get_me()
        print(f"   Logged in as: {me.first_name} (@{me.username})")
    else:
        print("\n❌ Authentication failed.")
    
    await client.disconnect()
