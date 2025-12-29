"""
Tests for price tolerance checker.
"""

import pytest
import sys
sys.path.insert(0, str(__file__).rsplit('/tests', 1)[0])

from src.tolerance_checker import (
    check_price_tolerance,
    get_limit_order_price,
    calculate_price_deviation,
    is_price_favorable,
)


class TestCheckPriceTolerance:
    """Tests for price tolerance checking."""
    
    def test_within_tolerance_3_percent(self):
        """Price within 3% should pass."""
        is_within, deviation = check_price_tolerance(
            current_price=0.2060,
            entry_price=0.2000,
            tolerance_percent=0.03
        )
        assert is_within == True
        assert abs(deviation - 0.03) < 0.001
    
    def test_exceed_tolerance(self):
        """Price exceeding tolerance should fail."""
        is_within, deviation = check_price_tolerance(
            current_price=0.2100,
            entry_price=0.2000,
            tolerance_percent=0.03
        )
        assert is_within == False
        assert abs(deviation - 0.05) < 0.001
    
    def test_exact_tolerance(self):
        """Price at exact tolerance should pass."""
        is_within, deviation = check_price_tolerance(
            current_price=1.03,
            entry_price=1.00,
            tolerance_percent=0.03
        )
        assert is_within == True
    
    def test_entry_range_within(self):
        """Price within entry range should have 0% deviation."""
        is_within, deviation = check_price_tolerance(
            current_price=0.04000,
            entry_price=None,
            tolerance_percent=0.03,
            entry_price_low=0.03950,
            entry_price_high=0.04040
        )
        assert is_within == True
        assert deviation == 0.0
    
    def test_entry_range_above(self):
        """Price above entry range should use upper boundary."""
        is_within, deviation = check_price_tolerance(
            current_price=0.04100,
            entry_price=None,
            tolerance_percent=0.03,
            entry_price_low=0.03950,
            entry_price_high=0.04040
        )
        # deviation = (0.04100 - 0.04040) / 0.04040 = ~1.49%
        assert is_within == True
        assert deviation < 0.02
    
    def test_entry_range_below(self):
        """Price below entry range should use lower boundary."""
        is_within, deviation = check_price_tolerance(
            current_price=0.03800,
            entry_price=None,
            tolerance_percent=0.05,
            entry_price_low=0.03950,
            entry_price_high=0.04040
        )
        # deviation = (0.03950 - 0.03800) / 0.03950 = ~3.8%
        assert is_within == True


class TestGetLimitOrderPrice:
    """Tests for limit order price calculation."""
    
    def test_long_order_price(self):
        """LONG order should be slightly above current."""
        limit = get_limit_order_price(100.0, "LONG", 0.001)
        assert limit == 100.1
    
    def test_short_order_price(self):
        """SHORT order should be slightly below current."""
        limit = get_limit_order_price(100.0, "SHORT", 0.001)
        assert limit == 99.9
    
    def test_custom_offset(self):
        """Custom offset should be applied correctly."""
        limit = get_limit_order_price(100.0, "LONG", 0.01)
        assert limit == 101.0


class TestCalculatePriceDeviation:
    """Tests for price deviation calculation."""
    
    def test_positive_deviation(self):
        """Positive deviation should be calculated correctly."""
        assert abs(calculate_price_deviation(100, 103) - 0.03) < 0.001
    
    def test_negative_deviation(self):
        """Negative deviation should be absolute."""
        assert abs(calculate_price_deviation(100, 97) - 0.03) < 0.001
    
    def test_zero_deviation(self):
        """Same prices should have zero deviation."""
        assert calculate_price_deviation(100, 100) == 0
    
    def test_zero_reference(self):
        """Zero reference should return infinity."""
        assert calculate_price_deviation(0, 100) == float('inf')


class TestIsPriceFavorable:
    """Tests for favorable price detection."""
    
    def test_long_lower_favorable(self):
        """For LONG, lower price is favorable."""
        is_favorable, improvement = is_price_favorable(95, 100, "LONG")
        assert is_favorable == True
        assert improvement > 0
    
    def test_long_higher_unfavorable(self):
        """For LONG, higher price is unfavorable."""
        is_favorable, improvement = is_price_favorable(105, 100, "LONG")
        assert is_favorable == False
    
    def test_short_higher_favorable(self):
        """For SHORT, higher price is favorable."""
        is_favorable, improvement = is_price_favorable(105, 100, "SHORT")
        assert is_favorable == True
        assert improvement > 0
    
    def test_short_lower_unfavorable(self):
        """For SHORT, lower price is unfavorable."""
        is_favorable, improvement = is_price_favorable(95, 100, "SHORT")
        assert is_favorable == False
    
    def test_same_price(self):
        """Same price should be favorable (equal)."""
        is_favorable, improvement = is_price_favorable(100, 100, "LONG")
        assert is_favorable == True
        assert improvement == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
