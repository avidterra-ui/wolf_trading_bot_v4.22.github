"""
Tests for trade executor v4.2.
Tests multi-signal support, max trades per day, LIMIT order only policy,
and BingX USDT-M Swap V2 compliance (BASE-USDT symbol format).
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import (
    RuntimeConfig, TradeSignal, TradeDirection, SignalSource,
    TPSLMode, OrderDetails, OrderStatus
)
from src.trade_executor import TradeExecutor, DryRunExecutor


class TestDuplicateTradeDetection:
    """Test duplicate trade detection with configurable max trades."""
    
    @pytest.fixture
    def config_single_trade(self):
        """Config allowing only 1 trade per symbol/direction per day."""
        return RuntimeConfig(
            enable_vip_signals=True,
            enable_free_signals=True,
            position_size_usdt=1.0,
            leverage=50,
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,
            vip_tp_sl_mode=TPSLMode.MANUAL,
            manual_tp_percent=10.0,
            manual_sl_percent=2.0,
            price_tolerance_percent=0.03,
            dry_run=True,
            allow_opposite_direction_same_day=True,
            max_same_direction_trades_per_day=1,
            max_trades_per_day=10,
        )
    
    @pytest.fixture
    def config_multi_trade(self):
        """Config allowing 3 trades per symbol/direction per day."""
        return RuntimeConfig(
            enable_vip_signals=True,
            enable_free_signals=True,
            position_size_usdt=1.0,
            leverage=50,
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,
            vip_tp_sl_mode=TPSLMode.MANUAL,
            manual_tp_percent=10.0,
            manual_sl_percent=2.0,
            price_tolerance_percent=0.03,
            dry_run=True,
            allow_opposite_direction_same_day=True,
            max_same_direction_trades_per_day=3,
            max_trades_per_day=10,
        )
    
    @pytest.fixture
    def config_unlimited(self):
        """Config allowing unlimited trades per symbol/direction per day."""
        return RuntimeConfig(
            enable_vip_signals=True,
            enable_free_signals=True,
            position_size_usdt=1.0,
            leverage=50,
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,
            vip_tp_sl_mode=TPSLMode.MANUAL,
            manual_tp_percent=10.0,
            manual_sl_percent=2.0,
            price_tolerance_percent=0.03,
            dry_run=True,
            allow_opposite_direction_same_day=True,
            max_same_direction_trades_per_day=0,  # Unlimited
            max_trades_per_day=0,  # Unlimited
        )
    
    @pytest.fixture
    def config_no_opposite(self):
        """Config NOT allowing opposite direction trades."""
        return RuntimeConfig(
            enable_vip_signals=True,
            enable_free_signals=True,
            position_size_usdt=1.0,
            leverage=50,
            free_tp_sl_mode=TPSLMode.MANUAL,
            vip_tp_sl_mode=TPSLMode.MANUAL,
            manual_tp_percent=10.0,
            manual_sl_percent=2.0,
            price_tolerance_percent=0.03,
            dry_run=True,
            allow_opposite_direction_same_day=False,
            max_same_direction_trades_per_day=1,
            max_trades_per_day=10,
        )
    
    def test_first_trade_allowed(self, config_single_trade):
        """First trade on a symbol should be allowed."""
        executor = DryRunExecutor(config_single_trade)
        
        # First LONG on BTC-USDT should be allowed (BingX Swap V2 format)
        is_dup = executor._is_duplicate_trade("BTC-USDT", TradeDirection.LONG)
        assert is_dup is False
    
    def test_same_direction_blocked_after_max(self, config_single_trade):
        """Same direction should be blocked after max reached."""
        executor = DryRunExecutor(config_single_trade)
        
        # Execute first LONG
        executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
        
        # Second LONG should be blocked
        is_dup = executor._is_duplicate_trade("BTC-USDT", TradeDirection.LONG)
        assert is_dup is True
    
    def test_opposite_direction_allowed_when_enabled(self, config_single_trade):
        """Opposite direction should be allowed when config allows it."""
        executor = DryRunExecutor(config_single_trade)
        
        # Execute LONG
        executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
        
        # SHORT should still be allowed
        is_dup = executor._is_duplicate_trade("BTC-USDT", TradeDirection.SHORT)
        assert is_dup is False
    
    def test_opposite_direction_blocked_when_disabled(self, config_no_opposite):
        """Opposite direction should be blocked when config disables it."""
        executor = DryRunExecutor(config_no_opposite)
        
        # Execute LONG
        executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
        
        # SHORT should be blocked
        is_dup = executor._is_duplicate_trade("BTC-USDT", TradeDirection.SHORT)
        assert is_dup is True
    
    def test_multiple_same_direction_allowed_with_higher_max(self, config_multi_trade):
        """Multiple same direction trades allowed up to max."""
        executor = DryRunExecutor(config_multi_trade)
        
        # Execute 3 LONGs (using BingX Swap V2 format)
        for i in range(3):
            is_dup = executor._is_duplicate_trade("BTC-USDT", TradeDirection.LONG)
            assert is_dup is False, f"Trade {i+1} should be allowed"
            executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
        
        # 4th LONG should be blocked
        is_dup = executor._is_duplicate_trade("BTC-USDT", TradeDirection.LONG)
        assert is_dup is True, "4th trade should be blocked"
    
    def test_unlimited_trades_allowed(self, config_unlimited):
        """Unlimited trades should be allowed when max=0."""
        executor = DryRunExecutor(config_unlimited)
        
        # Execute 10 LONGs - all should be allowed (using BingX Swap V2 format)
        for i in range(10):
            is_dup = executor._is_duplicate_trade("BTC-USDT", TradeDirection.LONG)
            assert is_dup is False, f"Trade {i+1} should be allowed (unlimited mode)"
            executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
    
    def test_different_symbols_independent(self, config_single_trade):
        """Different symbols should have independent tracking."""
        executor = DryRunExecutor(config_single_trade)
        
        # Execute LONG on BTC-USDT
        executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
        
        # LONG on ETH-USDT should still be allowed
        is_dup = executor._is_duplicate_trade("ETH-USDT", TradeDirection.LONG)
        assert is_dup is False
    
    def test_trade_count_tracking(self, config_multi_trade):
        """Trade counts should be tracked correctly."""
        executor = DryRunExecutor(config_multi_trade)
        
        # Initially 0 (using BingX Swap V2 format)
        count = executor._get_trade_count("BTC-USDT", TradeDirection.LONG)
        assert count == 0
        
        # After 1 trade
        executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
        count = executor._get_trade_count("BTC-USDT", TradeDirection.LONG)
        assert count == 1
        
        # After 2 trades
        executor._mark_trade_executed("BTC-USDT", TradeDirection.LONG)
        count = executor._get_trade_count("BTC-USDT", TradeDirection.LONG)
        assert count == 2
        
        # SHORT should still be 0
        count = executor._get_trade_count("BTC-USDT", TradeDirection.SHORT)
        assert count == 0


class TestMaxTradesPerDay:
    """Test max_trades_per_day limit (v4.1 feature)."""
    
    @pytest.fixture
    def config_daily_limit(self):
        """Config with 5 trades per day limit."""
        return RuntimeConfig(
            position_size_usdt=1.0,
            leverage=50,
            dry_run=True,
            max_trades_per_day=5,
            max_same_direction_trades_per_day=10,  # Higher than daily
        )
    
    def test_daily_limit_not_reached(self, config_daily_limit):
        """Should allow trades when daily limit not reached."""
        executor = DryRunExecutor(config_daily_limit)
        
        assert executor._check_daily_limit() is False
    
    def test_daily_limit_reached(self, config_daily_limit):
        """Should block trades when daily limit reached."""
        executor = DryRunExecutor(config_daily_limit)
        
        # Execute 5 trades
        for i in range(5):
            executor._increment_daily_count()
        
        assert executor._check_daily_limit() is True
    
    def test_daily_limit_zero_means_unlimited(self):
        """max_trades_per_day=0 should mean unlimited."""
        config = RuntimeConfig(
            dry_run=True,
            max_trades_per_day=0,
        )
        executor = DryRunExecutor(config)
        
        # Execute 100 trades
        for _ in range(100):
            executor._increment_daily_count()
        
        # Should still not be limited
        assert executor._check_daily_limit() is False
    
    def test_daily_count_tracking(self, config_daily_limit):
        """Daily count should be tracked correctly."""
        executor = DryRunExecutor(config_daily_limit)
        
        assert executor._get_daily_count() == 0
        
        executor._increment_daily_count()
        assert executor._get_daily_count() == 1
        
        executor._increment_daily_count()
        assert executor._get_daily_count() == 2


class TestDryRunExecutor:
    """Test dry run executor."""
    
    @pytest.fixture
    def config(self):
        return RuntimeConfig(
            enable_vip_signals=True,
            enable_free_signals=True,
            position_size_usdt=1.0,
            leverage=50,
            free_tp_sl_mode=TPSLMode.MANUAL,
            vip_tp_sl_mode=TPSLMode.MANUAL,
            manual_tp_percent=10.0,
            manual_sl_percent=2.0,
            price_tolerance_percent=0.03,
            dry_run=True,
            allow_opposite_direction_same_day=True,
            max_same_direction_trades_per_day=2,
            max_trades_per_day=10,
        )
    
    @pytest.fixture
    def sample_signal(self):
        # Using BingX USDT-M Swap V2 format: BASE-USDT
        return TradeSignal(
            source=SignalSource.FREE,
            symbol="BTC-USDT",  # BingX Swap V2 format
            direction=TradeDirection.LONG,
            entry_price=50000.0,
            take_profits=[51000.0, 52000.0],
            stop_loss=49000.0,
            leverage=50,
            timestamp=datetime.now(),
            raw_text="Test signal",
            message_id=12345,
        )
    
    @pytest.mark.asyncio
    async def test_dry_run_executes_signal(self, config, sample_signal):
        """Dry run should simulate trade execution."""
        executor = DryRunExecutor(config)
        
        with patch('src.trade_executor.feedback'):
            order = await executor.execute_signal(sample_signal)
        
        assert order is not None
        assert order.symbol == "BTC-USDT"  # BingX Swap V2 format
        assert order.direction == TradeDirection.LONG
        assert order.status == OrderStatus.FILLED
        assert "DRY_RUN" in order.order_id
    
    @pytest.mark.asyncio
    async def test_dry_run_respects_duplicate_limit(self, config, sample_signal):
        """Dry run should respect duplicate trade limits."""
        executor = DryRunExecutor(config)
        
        with patch('src.trade_executor.feedback'):
            # First trade should succeed
            order1 = await executor.execute_signal(sample_signal)
            assert order1 is not None
            
            # Second trade should succeed (max=2)
            order2 = await executor.execute_signal(sample_signal)
            assert order2 is not None
            
            # Third trade should be blocked
            order3 = await executor.execute_signal(sample_signal)
            assert order3 is None
    
    @pytest.mark.asyncio
    async def test_dry_run_respects_daily_limit(self, sample_signal):
        """Dry run should respect daily trade limits."""
        config = RuntimeConfig(
            dry_run=True,
            max_trades_per_day=2,
            max_same_direction_trades_per_day=10,
        )
        executor = DryRunExecutor(config)
        
        with patch('src.trade_executor.feedback'):
            # First trade - BTC-USDT LONG (BingX Swap V2 format)
            signal1 = TradeSignal(
                source=SignalSource.FREE,
                symbol="BTC-USDT",  # BingX Swap V2 format
                direction=TradeDirection.LONG,
                entry_price=50000.0,
            )
            order1 = await executor.execute_signal(signal1)
            assert order1 is not None
            
            # Second trade - ETH-USDT LONG (different symbol)
            signal2 = TradeSignal(
                source=SignalSource.FREE,
                symbol="ETH-USDT",  # BingX Swap V2 format
                direction=TradeDirection.LONG,
                entry_price=2000.0,
            )
            order2 = await executor.execute_signal(signal2)
            assert order2 is not None
            
            # Third trade - should be blocked by daily limit
            signal3 = TradeSignal(
                source=SignalSource.FREE,
                symbol="XRP-USDT",  # BingX Swap V2 format
                direction=TradeDirection.LONG,
                entry_price=0.5,
            )
            order3 = await executor.execute_signal(signal3)
            assert order3 is None  # Blocked by daily limit


class TestRuntimeConfigDefaults:
    """Test RuntimeConfig default values for v4.1."""
    
    def test_default_max_same_direction_trades(self):
        """Default max_same_direction_trades_per_day should be 1."""
        config = RuntimeConfig()
        assert config.max_same_direction_trades_per_day == 1
    
    def test_default_max_trades_per_day(self):
        """Default max_trades_per_day should be 5."""
        config = RuntimeConfig()
        assert config.max_trades_per_day == 5
    
    def test_default_tp_sl_modes(self):
        """Default TP/SL modes should be correct."""
        config = RuntimeConfig()
        assert config.free_tp_sl_mode == TPSLMode.FROM_SIGNAL
        assert config.vip_tp_sl_mode == TPSLMode.MANUAL
    
    def test_default_sl_max(self):
        """Default SL max should be 5%."""
        config = RuntimeConfig()
        assert config.sl_max_percent == 5.0
    
    def test_to_dict_includes_v41_fields(self):
        """to_dict() should include v4.1 configuration fields."""
        config = RuntimeConfig(
            allow_opposite_direction_same_day=True,
            max_same_direction_trades_per_day=5,
            max_trades_per_day=10,
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,
            vip_tp_sl_mode=TPSLMode.MANUAL,
        )
        d = config.to_dict()
        
        assert 'allow_opposite_direction_same_day' in d
        assert d['allow_opposite_direction_same_day'] is True
        assert 'max_same_direction_trades_per_day' in d
        assert d['max_same_direction_trades_per_day'] == 5
        assert 'max_trades_per_day' in d
        assert d['max_trades_per_day'] == 10
        assert 'free_tp_sl_mode' in d
        assert d['free_tp_sl_mode'] == 'from_signal'
        assert 'vip_tp_sl_mode' in d
        assert d['vip_tp_sl_mode'] == 'manual'


class TestStatsTracking:
    """Test statistics tracking for v4.2."""
    
    def test_stats_include_daily_limit_skips(self):
        """Stats should track trades skipped due to daily limit."""
        config = RuntimeConfig(dry_run=True, max_trades_per_day=5)
        executor = DryRunExecutor(config)
        
        assert 'trades_skipped_daily_limit' in executor.stats
        assert executor.stats['trades_skipped_daily_limit'] == 0
    
    def test_stats_include_symbol_invalid_skips(self):
        """Stats should track trades skipped due to invalid symbol."""
        config = RuntimeConfig(dry_run=True)
        executor = DryRunExecutor(config)
        
        assert 'trades_skipped_symbol_invalid' in executor.stats
        assert executor.stats['trades_skipped_symbol_invalid'] == 0
    
    def test_stats_include_leverage_failed_skips(self):
        """Stats should track trades skipped due to leverage setting failure."""
        config = RuntimeConfig(dry_run=True)
        executor = DryRunExecutor(config)
        
        assert 'trades_skipped_leverage_failed' in executor.stats
        assert executor.stats['trades_skipped_leverage_failed'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
