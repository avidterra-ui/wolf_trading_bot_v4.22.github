"""
Trade executor for Wolf Trading Bot v4.2.
Handles order placement and management with safety checks.

CRITICAL v4.2 REQUIREMENTS (BingX USDT-M Swap V2 Compliance):
- STRICT Limit-Order Execution: NO MARKET ORDERS permitted
- Daily trade limit check (max_trades_per_day)
- Duplicate trade prevention per symbol/direction
- Unfilled orders are CANCELLED, never converted to market
- MANDATORY symbol validation via contracts endpoint before ANY trade
- MANDATORY leverage setting (integer, LONG/SHORT) before ANY order
- Symbol format: BASE-USDT (with dash)
"""

import asyncio
from datetime import datetime, date
from typing import Dict, Set, Optional, Tuple

from .models import (
    TradeSignal, RuntimeConfig, OrderDetails, OrderStatus,
    TradeDirection, TPSLCalculation
)
from .bingx_client import (
    SecureBingXClient, BingXError, InsufficientBalanceError,
    SymbolNotFoundError, OrderFailedError, SymbolValidationError,
    LeverageSetError
)
from .tolerance_checker import check_price_tolerance, get_limit_order_price
from .tp_sl_calculator import get_tp_sl_for_signal
from .utils.logging_setup import get_logger
from . import feedback

logger = get_logger(__name__)


class TradeExecutor:
    """
    Handles trade execution with safety checks.
    
    Features (v4.2 - BingX USDT-M Swap V2 Compliance):
    - MANDATORY symbol validation via /openApi/swap/v2/quote/contracts
    - Symbol MUST match exactly (e.g., TRADOOR-USDT) with status=1 and apiStateOpen=true
    - MANDATORY leverage setting before ANY order (integer leverage, LONG/SHORT side)
    - If leverage fails -> DO NOT place order
    - Duplicate trade prevention (per symbol/direction per day)
    - Configurable max trades per symbol/direction per day
    - Maximum trades per day (total daily limit)
    - Price tolerance validation
    - TP/SL order placement
    - STRICT LIMIT ORDERS ONLY - NO MARKET ORDERS
    - Dry run mode
    """
    
    def __init__(
        self,
        bingx_client: SecureBingXClient,
        config: RuntimeConfig
    ):
        """
        Initialize trade executor.
        
        Args:
            bingx_client: BingX API client
            config: Runtime configuration
        """
        self.client = bingx_client
        self.config = config
        
        # Track executed trades with counts: {date: {(symbol, direction): count}}
        self._executed_trades: Dict[date, Dict[Tuple[str, str], int]] = {}
        
        # Track total trades per day: {date: count}
        self._daily_trade_count: Dict[date, int] = {}
        
        # Statistics
        self.stats = {
            'signals_received': 0,
            'trades_executed': 0,
            'trades_skipped_duplicate': 0,
            'trades_skipped_tolerance': 0,
            'trades_skipped_daily_limit': 0,
            'trades_skipped_symbol_invalid': 0,
            'trades_skipped_leverage_failed': 0,
            'trades_failed': 0,
        }
    
    def _get_today_trades(self) -> Dict[Tuple[str, str], int]:
        """Get dict of trades executed today with counts."""
        today = date.today()
        if today not in self._executed_trades:
            self._executed_trades[today] = {}
        
        # Clean up old dates
        old_dates = [d for d in self._executed_trades if d < today]
        for d in old_dates:
            del self._executed_trades[d]
        
        return self._executed_trades[today]
    
    def _get_daily_count(self) -> int:
        """Get total number of trades executed today."""
        today = date.today()
        
        # Clean up old dates
        old_dates = [d for d in self._daily_trade_count if d < today]
        for d in old_dates:
            del self._daily_trade_count[d]
        
        return self._daily_trade_count.get(today, 0)
    
    def _increment_daily_count(self):
        """Increment the daily trade count."""
        today = date.today()
        self._daily_trade_count[today] = self._daily_trade_count.get(today, 0) + 1
    
    def _check_daily_limit(self) -> bool:
        """
        Check if daily trade limit has been reached.
        
        Returns:
            True if daily limit reached (should skip trade)
            False if can still trade
        """
        max_daily = self.config.max_trades_per_day
        if max_daily == 0:
            return False  # Unlimited
        
        current_count = self._get_daily_count()
        if current_count >= max_daily:
            logger.warning(f"Daily trade limit reached: {current_count}/{max_daily}")
            return True
        
        return False
    
    def _get_trade_count(self, symbol: str, direction: TradeDirection) -> int:
        """Get the number of times this symbol/direction was traded today."""
        today_trades = self._get_today_trades()
        trade_key = (symbol, direction.value)
        return today_trades.get(trade_key, 0)
    
    def _is_duplicate_trade(self, symbol: str, direction: TradeDirection) -> bool:
        """
        Check if this trade exceeds the allowed count for today.
        
        Behavior depends on:
        - allow_opposite_direction_same_day: Allow LONG and SHORT on same pair
        - max_same_direction_trades_per_day: Max trades per symbol/direction (0 = unlimited)
        
        Returns:
            True if trade should be blocked (duplicate/exceeded limit)
            False if trade is allowed
        """
        today_trades = self._get_today_trades()
        trade_key = (symbol, direction.value)
        
        # Get current count for this exact trade (same symbol + same direction)
        current_count = today_trades.get(trade_key, 0)
        max_allowed = self.config.max_same_direction_trades_per_day
        
        # Check if we've exceeded the max for this symbol/direction
        if max_allowed > 0 and current_count >= max_allowed:
            logger.debug(f"Max trades reached for {symbol} {direction.value}: {current_count}/{max_allowed}")
            return True
        
        # If NOT allowing opposite directions, also check for any trade on this symbol
        if not self.config.allow_opposite_direction_same_day:
            # Check if ANY direction was traded on this symbol today
            opposite_direction = TradeDirection.SHORT if direction == TradeDirection.LONG else TradeDirection.LONG
            opposite_key = (symbol, opposite_direction.value)
            opposite_count = today_trades.get(opposite_key, 0)
            if opposite_count > 0:
                logger.debug(f"Opposite direction already traded for {symbol}: {opposite_direction.value}")
                return True
        else:
            # Log scalping mode when opposite direction exists
            opposite_direction = TradeDirection.SHORT if direction == TradeDirection.LONG else TradeDirection.LONG
            opposite_key = (symbol, opposite_direction.value)
            opposite_count = today_trades.get(opposite_key, 0)
            if opposite_count > 0:
                feedback.log_same_pair_opposite_direction(symbol, direction.value, opposite_direction.value)
        
        return False
    
    def _mark_trade_executed(self, symbol: str, direction: TradeDirection):
        """Mark a trade as executed for today (increments count)."""
        today_trades = self._get_today_trades()
        trade_key = (symbol, direction.value)
        today_trades[trade_key] = today_trades.get(trade_key, 0) + 1
        logger.debug(f"Trade count for {symbol} {direction.value}: {today_trades[trade_key]}")
        
        # Also increment daily total
        self._increment_daily_count()
    
    async def execute_signal(self, signal: TradeSignal) -> Optional[OrderDetails]:
        """
        Execute a trading signal with MANDATORY BingX USDT-M Swap V2 compliance.
        
        CRITICAL EXECUTION ORDER (per BingX API requirements):
        1) Extract symbol from caption (already done by parser)
        2) Normalize to BASE-USDT format (already done by parser)
        3) MANDATORY: Validate symbol via contracts endpoint
        4) MANDATORY: Set leverage (must succeed before order)
        5) ONLY AFTER success -> place LIMIT order
        
        If symbol validation OR leverage setting fails -> DO NOT place order.
        Only LIMIT orders are used. NO MARKET ORDERS.
        If order not filled within timeout, it is CANCELLED (not converted to market).
        
        Args:
            signal: The trading signal to execute
            
        Returns:
            OrderDetails if executed, None if skipped
        """
        self.stats['signals_received'] += 1
        
        logger.info(f"{'='*60}")
        logger.info(f"EXECUTING SIGNAL: {signal.symbol} {signal.direction.value}")
        logger.info(f"{'='*60}")
        
        try:
            # Step 1: Check daily trade limit
            if self._check_daily_limit():
                feedback.log_daily_limit_reached(
                    self._get_daily_count(),
                    self.config.max_trades_per_day
                )
                self.stats['trades_skipped_daily_limit'] += 1
                return None
            
            # Step 2: Check for duplicate
            if self._is_duplicate_trade(signal.symbol, signal.direction):
                feedback.log_duplicate_trade(signal.symbol, signal.direction.value)
                self.stats['trades_skipped_duplicate'] += 1
                return None
            
            # ════════════════════════════════════════════════════════════════
            # STEP 3: MANDATORY SYMBOL VALIDATION (BingX USDT-M Swap V2)
            # ════════════════════════════════════════════════════════════════
            # Per API requirements:
            # - Call GET /openApi/swap/v2/quote/contracts
            # - Symbol MUST match exactly (e.g., TRADOOR-USDT)
            # - status MUST == 1
            # - apiStateOpen MUST == "true"
            # If no match: DO NOT PLACE TRADE, log error, skip safely
            # ════════════════════════════════════════════════════════════════
            logger.info(f"Step 3: Validating symbol {signal.symbol} via contracts endpoint...")
            
            is_valid, contract_info, validation_error = await self.client.validate_symbol(signal.symbol)
            
            if not is_valid:
                logger.error(f"SYMBOL VALIDATION FAILED: {validation_error}")
                feedback.log_symbol_not_found(signal.symbol)
                feedback.log_error("Symbol validation failed", validation_error)
                self.stats['trades_skipped_symbol_invalid'] += 1
                return None
            
            logger.info(f"Symbol {signal.symbol} validated successfully")
            
            # ════════════════════════════════════════════════════════════════
            # STEP 4: MANDATORY LEVERAGE SETTING (BingX USDT-M Swap V2)
            # ════════════════════════════════════════════════════════════════
            # Per API requirements:
            # - POST /openApi/swap/v2/trade/leverage
            # - leverage MUST be INTEGER (not string)
            # - side MUST be "LONG" or "SHORT" (not "BUY"/"SELL")
            # - Symbol MUST match contracts list exactly
            # If leverage setting fails: DO NOT PLACE ORDER, skip safely
            # ════════════════════════════════════════════════════════════════
            logger.info(f"Step 4: Setting leverage for {signal.symbol}...")
            
            try:
                actual_leverage = await self.client.set_leverage(
                    signal.symbol,
                    int(self.config.leverage),  # MUST be integer
                    signal.direction.value      # "LONG" or "SHORT"
                )
                logger.info(f"Leverage set successfully: {actual_leverage}x")
            except LeverageSetError as e:
                logger.error(f"LEVERAGE SETTING FAILED: {e}")
                feedback.log_error("Leverage setting failed - trade skipped", str(e))
                self.stats['trades_skipped_leverage_failed'] += 1
                return None
            
            # Step 5: Get current price
            current_price = await self.client.get_current_price(signal.symbol)
            if not current_price:
                feedback.log_error("Failed to get current price", signal.symbol)
                self.stats['trades_failed'] += 1
                return None
            
            # Step 6: Determine entry price for tolerance check
            entry_price = signal.entry_reference or current_price
            
            # Step 7: Check price tolerance
            is_within, deviation = check_price_tolerance(
                current_price=current_price,
                entry_price=entry_price,
                tolerance_percent=self.config.price_tolerance_percent,
                entry_price_low=signal.entry_price_low,
                entry_price_high=signal.entry_price_high,
            )
            
            if not is_within:
                feedback.log_tolerance_exceeded(
                    deviation,
                    self.config.price_tolerance_percent,
                    current_price,
                    entry_price
                )
                self.stats['trades_skipped_tolerance'] += 1
                return None
            
            # Step 8: Calculate position size
            quantity = self.client.calculate_quantity(
                self.config.position_size_usdt,
                current_price,
                contract_info
            )
            
            # Step 9: Calculate TP/SL (based on signal source and configured mode)
            tp_sl = get_tp_sl_for_signal(signal, self.config, current_price)
            
            # Step 10: Calculate limit order price
            limit_price = get_limit_order_price(
                current_price,
                signal.direction.value,
                offset_percent=0.001
            )
            
            # Create order details
            order = OrderDetails(
                symbol=signal.symbol,
                direction=signal.direction,
                entry_price=limit_price,
                quantity=quantity,
                leverage=actual_leverage,
                tp_price=tp_sl.tp_price,
                sl_price=tp_sl.sl_price,
                tp_percent=tp_sl.tp_percent_without_leverage,
                sl_percent=tp_sl.sl_percent_without_leverage,
                status=OrderStatus.PENDING,
            )
            
            # Step 11: Execute or dry run
            if self.config.dry_run:
                feedback.log_dry_run(order, actual_leverage)
                order.status = OrderStatus.FILLED  # Simulate fill
                order.order_id = f"DRY_RUN_{datetime.now().timestamp()}"
            else:
                # Place actual LIMIT order (NEVER market)
                order_id = await self.client.place_limit_order(
                    symbol=signal.symbol,
                    direction=signal.direction,
                    quantity=quantity,
                    price=limit_price,
                    tp_price=tp_sl.tp_price,
                    sl_price=tp_sl.sl_price,
                )
                
                if not order_id:
                    feedback.log_error("Order placement failed", signal.symbol)
                    self.stats['trades_failed'] += 1
                    return None
                
                order.order_id = order_id
                
                # Wait for fill
                final_status = await self.client.wait_for_fill(
                    symbol=signal.symbol,
                    order_id=order_id,
                    timeout_seconds=10
                )
                
                order.status = final_status
                
                if final_status == OrderStatus.FILLED:
                    feedback.log_trade_executed(order, actual_leverage)
                elif final_status == OrderStatus.PENDING:
                    # CRITICAL: Cancel unfilled order - DO NOT convert to market
                    await self.client.cancel_order(signal.symbol, order_id)
                    feedback.log_order_cancelled(order_id, "Timeout - not filled (LIMIT ONLY policy)")
                    order.status = OrderStatus.CANCELLED
                    self.stats['trades_failed'] += 1
                    return None
            
            # Mark as executed
            self._mark_trade_executed(signal.symbol, signal.direction)
            self.stats['trades_executed'] += 1
            
            return order
            
        except InsufficientBalanceError:
            feedback.log_insufficient_balance()
            self.stats['trades_failed'] += 1
            return None
            
        except (SymbolNotFoundError, SymbolValidationError) as e:
            logger.error(f"Symbol error: {e}")
            feedback.log_symbol_not_found(signal.symbol)
            self.stats['trades_skipped_symbol_invalid'] += 1
            return None
        
        except LeverageSetError as e:
            logger.error(f"Leverage error: {e}")
            feedback.log_error("Leverage setting failed", str(e))
            self.stats['trades_skipped_leverage_failed'] += 1
            return None
            
        except OrderFailedError as e:
            feedback.log_error("Order failed", str(e))
            self.stats['trades_failed'] += 1
            return None
            
        except BingXError as e:
            feedback.log_api_error(str(e))
            self.stats['trades_failed'] += 1
            return None
            
        except Exception as e:
            logger.exception(f"Unexpected error executing signal: {e}")
            feedback.log_error("Unexpected error", str(e))
            self.stats['trades_failed'] += 1
            return None
    
    def get_stats_summary(self) -> str:
        """Get statistics summary."""
        return (
            f"Signals: {self.stats['signals_received']} | "
            f"Executed: {self.stats['trades_executed']} | "
            f"Duplicates: {self.stats['trades_skipped_duplicate']} | "
            f"Tolerance: {self.stats['trades_skipped_tolerance']} | "
            f"Daily Limit: {self.stats['trades_skipped_daily_limit']} | "
            f"Invalid Symbol: {self.stats['trades_skipped_symbol_invalid']} | "
            f"Leverage Failed: {self.stats['trades_skipped_leverage_failed']} | "
            f"Failed: {self.stats['trades_failed']}"
        )


class DryRunExecutor(TradeExecutor):
    """
    Trade executor that only simulates trades.
    Used for testing and paper trading.
    """
    
    def __init__(self, config: RuntimeConfig):
        """Initialize without actual BingX client."""
        self.client = None  # No actual client
        self.config = config
        self.config.dry_run = True  # Force dry run
        
        self._executed_trades: Dict[date, Dict[Tuple[str, str], int]] = {}
        self._daily_trade_count: Dict[date, int] = {}
        self.stats = {
            'signals_received': 0,
            'trades_executed': 0,
            'trades_skipped_duplicate': 0,
            'trades_skipped_tolerance': 0,
            'trades_skipped_daily_limit': 0,
            'trades_skipped_symbol_invalid': 0,
            'trades_skipped_leverage_failed': 0,
            'trades_failed': 0,
        }
    
    async def execute_signal(self, signal: TradeSignal) -> Optional[OrderDetails]:
        """Simulate trade execution."""
        self.stats['signals_received'] += 1
        
        # Check daily limit first
        if self._check_daily_limit():
            feedback.log_daily_limit_reached(
                self._get_daily_count(),
                self.config.max_trades_per_day
            )
            self.stats['trades_skipped_daily_limit'] += 1
            return None
        
        # Check duplicate using parent's method (respects allow_opposite_direction_same_day)
        if self._is_duplicate_trade(signal.symbol, signal.direction):
            feedback.log_duplicate_trade(signal.symbol, signal.direction.value)
            self.stats['trades_skipped_duplicate'] += 1
            return None
        
        # Use signal entry price or default
        entry_price = signal.entry_reference or 1.0
        
        # Calculate simulated values
        quantity = self.config.position_size_usdt / entry_price
        tp_sl = get_tp_sl_for_signal(signal, self.config, entry_price)
        
        order = OrderDetails(
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=entry_price,
            quantity=quantity,
            leverage=self.config.leverage,
            tp_price=tp_sl.tp_price,
            sl_price=tp_sl.sl_price,
            tp_percent=tp_sl.tp_percent_without_leverage,
            sl_percent=tp_sl.sl_percent_without_leverage,
            order_id=f"DRY_RUN_{datetime.now().timestamp()}",
            status=OrderStatus.FILLED,
        )
        
        feedback.log_dry_run(order, self.config.leverage)
        
        self._mark_trade_executed(signal.symbol, signal.direction)
        self.stats['trades_executed'] += 1
        
        return order
