"""
Tests for TP/SL calculator v4.1.
Tests separate modes for VIP (always manual) and FREE (from_signal or manual) signals.
"""

import pytest
import sys
sys.path.insert(0, str(__file__).rsplit('/tests', 1)[0])

from src.tp_sl_calculator import (
    convert_percent_with_leverage,
    convert_percent_without_leverage,
    enforce_sl_limits,
    calculate_tp_sl_prices,
    calculate_percent_from_prices,
    get_tp_sl_for_signal,
    SL_MIN_PERCENT,
    SL_MAX_PERCENT,
)
from src.models import (
    TradeDirection, TradeSignal, RuntimeConfig, TPSLMode, SignalSource
)


class TestLeverageConversion:
    """Tests for leverage percentage conversion."""
    
    def test_with_leverage_50x(self):
        """1% without leverage = 50% with 50× leverage."""
        assert convert_percent_with_leverage(1.0, 50) == 50.0
    
    def test_with_leverage_10_percent(self):
        """10% without leverage = 500% with 50× leverage."""
        assert convert_percent_with_leverage(10.0, 50) == 500.0
    
    def test_without_leverage(self):
        """50% with leverage = 1% without 50× leverage."""
        assert convert_percent_without_leverage(50.0, 50) == 1.0
    
    def test_round_trip(self):
        """Converting back and forth should preserve value."""
        original = 5.0
        with_lev = convert_percent_with_leverage(original, 50)
        without_lev = convert_percent_without_leverage(with_lev, 50)
        assert abs(without_lev - original) < 0.001


class TestEnforceSLLimits:
    """Tests for SL limit enforcement."""
    
    def test_within_limits(self):
        """SL within limits should be unchanged."""
        assert enforce_sl_limits(2.0) == 2.0
        assert enforce_sl_limits(3.0) == 3.0
    
    def test_below_minimum(self):
        """SL below minimum should be adjusted."""
        assert enforce_sl_limits(0.1) == SL_MIN_PERCENT
    
    def test_above_maximum(self):
        """SL above maximum should be capped."""
        assert enforce_sl_limits(10.0) == SL_MAX_PERCENT
        assert enforce_sl_limits(100.0) == SL_MAX_PERCENT
    
    def test_at_limits(self):
        """SL at limits should be unchanged."""
        assert enforce_sl_limits(SL_MIN_PERCENT) == SL_MIN_PERCENT
        assert enforce_sl_limits(SL_MAX_PERCENT) == SL_MAX_PERCENT
    
    def test_custom_max(self):
        """Custom max should be enforced."""
        assert enforce_sl_limits(10.0, sl_max_percent=3.0) == 3.0


class TestCalculateTPSLPrices:
    """Tests for TP/SL price calculation."""
    
    def test_long_tp_sl(self):
        """LONG TP should be above entry, SL below."""
        result = calculate_tp_sl_prices(
            entry_price=100.0,
            direction=TradeDirection.LONG,
            tp_percent=10.0,
            sl_percent=2.0,
            leverage=50
        )
        
        assert result.tp_price == 110.0
        assert result.sl_price == 98.0
        assert result.tp_percent_without_leverage == 10.0
        assert result.tp_percent_with_leverage == 500.0
        assert result.sl_percent_without_leverage == 2.0
        assert result.sl_percent_with_leverage == 100.0
    
    def test_short_tp_sl(self):
        """SHORT TP should be below entry, SL above."""
        result = calculate_tp_sl_prices(
            entry_price=100.0,
            direction=TradeDirection.SHORT,
            tp_percent=10.0,
            sl_percent=2.0,
            leverage=50
        )
        
        assert result.tp_price == 90.0
        assert result.sl_price == 102.0
    
    def test_sl_capped_at_5_percent(self):
        """SL should be HARD CAPPED at 5% (v4.1 requirement)."""
        result = calculate_tp_sl_prices(
            entry_price=100.0,
            direction=TradeDirection.LONG,
            tp_percent=10.0,
            sl_percent=10.0,  # Should be capped to 5%
            leverage=50
        )
        
        assert result.sl_percent_without_leverage == 5.0
        assert result.sl_price == 95.0
        assert result.sl_percent_with_leverage == 250.0


class TestCalculatePercentFromPrices:
    """Tests for percentage calculation from prices."""
    
    def test_long_profit(self):
        """LONG profit percentage should be calculated."""
        pct = calculate_percent_from_prices(100.0, 110.0, TradeDirection.LONG)
        assert abs(pct - 10.0) < 0.001
    
    def test_long_loss(self):
        """LONG loss percentage should be positive (for SL)."""
        pct = calculate_percent_from_prices(100.0, 95.0, TradeDirection.LONG)
        assert abs(pct - (-5.0)) < 0.001
    
    def test_short_profit(self):
        """SHORT profit percentage should be calculated."""
        pct = calculate_percent_from_prices(100.0, 90.0, TradeDirection.SHORT)
        assert abs(pct - 10.0) < 0.001


class TestVIPSignalTPSL:
    """Tests for VIP signal TP/SL - ALWAYS uses manual (v4.1 requirement)."""
    
    def test_vip_always_uses_manual(self):
        """VIP signals should ALWAYS use manual TP/SL regardless of mode."""
        config = RuntimeConfig(
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,  # This shouldn't matter for VIP
            vip_tp_sl_mode=TPSLMode.MANUAL,
            manual_tp_percent=15.0,
            manual_sl_percent=3.0,
            leverage=50
        )
        
        signal = TradeSignal(
            source=SignalSource.VIP,
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            # VIP signals don't have TP/SL in image
        )
        
        result = get_tp_sl_for_signal(signal, config, 100.0)
        
        assert result.tp_percent_without_leverage == 15.0
        assert result.sl_percent_without_leverage == 3.0
    
    def test_vip_ignores_signal_values(self):
        """VIP signals should use manual even if values are somehow present."""
        config = RuntimeConfig(
            manual_tp_percent=10.0,
            manual_sl_percent=2.0,
            leverage=50
        )
        
        signal = TradeSignal(
            source=SignalSource.VIP,
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            # Even if these are set, VIP should ignore them
            take_profits=[150.0],  # Would be 50%
            stop_loss=90.0,        # Would be 10%
        )
        
        result = get_tp_sl_for_signal(signal, config, 100.0)
        
        # Should use manual, not signal values
        assert result.tp_percent_without_leverage == 10.0
        assert result.sl_percent_without_leverage == 2.0


class TestFREESignalTPSL:
    """Tests for FREE signal TP/SL - can use from_signal or manual (v4.1)."""
    
    def test_free_from_signal_mode(self):
        """FREE signals should parse TP/SL from signal when mode=from_signal."""
        config = RuntimeConfig(
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,
            manual_tp_percent=10.0,  # Fallback
            manual_sl_percent=2.0,   # Fallback
            leverage=50
        )
        
        signal = TradeSignal(
            source=SignalSource.FREE,
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            take_profits=[112.0, 115.0],  # 12%
            stop_loss=96.0,                # 4%
        )
        
        result = get_tp_sl_for_signal(signal, config, 100.0)
        
        # Should use signal values
        assert abs(result.tp_percent_without_leverage - 12.0) < 0.1
        assert abs(result.sl_percent_without_leverage - 4.0) < 0.1
    
    def test_free_manual_mode(self):
        """FREE signals should use manual when mode=manual."""
        config = RuntimeConfig(
            free_tp_sl_mode=TPSLMode.MANUAL,
            manual_tp_percent=15.0,
            manual_sl_percent=3.0,
            leverage=50
        )
        
        signal = TradeSignal(
            source=SignalSource.FREE,
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            take_profits=[120.0],  # Would be 20%
            stop_loss=92.0,        # Would be 8%
        )
        
        result = get_tp_sl_for_signal(signal, config, 100.0)
        
        # Should use manual, not signal values
        assert result.tp_percent_without_leverage == 15.0
        assert result.sl_percent_without_leverage == 3.0
    
    def test_free_from_signal_with_fallback(self):
        """FREE signals should fall back to manual if no TP/SL in signal."""
        config = RuntimeConfig(
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,
            manual_tp_percent=10.0,
            manual_sl_percent=2.0,
            leverage=50
        )
        
        signal = TradeSignal(
            source=SignalSource.FREE,
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            # No TP/SL provided
        )
        
        result = get_tp_sl_for_signal(signal, config, 100.0)
        
        # Should use fallback (manual) values
        assert result.tp_percent_without_leverage == 10.0
        assert result.sl_percent_without_leverage == 2.0
    
    def test_free_signal_sl_hard_capped(self):
        """FREE signal SL should be hard capped at 5% even from signal."""
        config = RuntimeConfig(
            free_tp_sl_mode=TPSLMode.FROM_SIGNAL,
            sl_max_percent=5.0,
            leverage=50
        )
        
        signal = TradeSignal(
            source=SignalSource.FREE,
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            take_profits=[110.0],
            stop_loss=88.0,  # Would be 12% - should be capped!
        )
        
        result = get_tp_sl_for_signal(signal, config, 100.0)
        
        # SL should be capped at 5%
        assert result.sl_percent_without_leverage == 5.0
        assert result.sl_price == 95.0  # 100 - 5%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
