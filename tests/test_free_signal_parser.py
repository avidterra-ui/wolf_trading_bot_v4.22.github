"""
Tests for FREE signal parser.
"""

import pytest
import sys
sys.path.insert(0, str(__file__).rsplit('/tests', 1)[0])

from src.free_signal_parser import (
    normalize_symbol,
    extract_symbol,
    extract_direction,
    extract_entry_price,
    extract_take_profits,
    extract_stop_loss,
    extract_leverage,
    parse_free_signal,
)
from src.models import TradeDirection, SignalSource
from tests.fixtures.sample_messages import (
    FREE_SIGNAL_EXAMPLE,
    FREE_SIGNAL_SHORT,
    FREE_SIGNAL_ALT,
)


class TestNormalizeSymbol:
    """Tests for symbol normalization.
    
    BingX USDT-M Swap V2 format requires BASE-USDT (with dash).
    VALID:   BTC-USDT, ETH-USDT, TRADOOR-USDT
    INVALID: BTCUSDT, BTC/USDT
    """
    
    def test_already_normalized(self):
        """Already normalized symbol should stay in BASE-USDT format."""
        assert normalize_symbol("BTCUSDT") == "BTC-USDT"
        assert normalize_symbol("ETHUSDT") == "ETH-USDT"
    
    def test_already_correct_format(self):
        """Symbols already in BASE-USDT format should stay same."""
        assert normalize_symbol("BTC-USDT") == "BTC-USDT"
        assert normalize_symbol("TRADOOR-USDT") == "TRADOOR-USDT"
    
    def test_with_parentheses(self):
        """Symbol with parentheses should be normalized to BASE-USDT."""
        assert normalize_symbol("BTC(USDT)") == "BTC-USDT"
        assert normalize_symbol("THE(USDT)") == "THE-USDT"
    
    def test_with_slash(self):
        """Symbol with slash should be normalized to BASE-USDT."""
        assert normalize_symbol("BTC/USDT") == "BTC-USDT"
        assert normalize_symbol("BEAT/USDT") == "BEAT-USDT"
    
    def test_with_hash(self):
        """Symbol with hash should be normalized to BASE-USDT."""
        assert normalize_symbol("#ICNT") == "ICNT-USDT"
        assert normalize_symbol("#BTC") == "BTC-USDT"
    
    def test_with_dollar(self):
        """Symbol with dollar sign should be normalized to BASE-USDT."""
        assert normalize_symbol("$ICNT") == "ICNT-USDT"
    
    def test_lowercase(self):
        """Lowercase should be converted to uppercase with dash."""
        assert normalize_symbol("btcusdt") == "BTC-USDT"
    
    def test_with_spaces(self):
        """Spaces should be removed and format should be BASE-USDT."""
        assert normalize_symbol("BTC USDT") == "BTC-USDT"
        assert normalize_symbol("1000LUNC (USDT)") == "1000LUNC-USDT"
    
    def test_with_degree_symbol(self):
        """Degree symbol (from captions like #TRADOOR/USDT°) should be removed."""
        assert normalize_symbol("#TRADOOR/USDT°") == "TRADOOR-USDT"


class TestExtractSymbol:
    """Tests for symbol extraction - returns BASE-USDT format."""
    
    def test_coin_name_format(self):
        """COIN NAME format should be extracted in BASE-USDT format."""
        assert extract_symbol(FREE_SIGNAL_EXAMPLE) == "1000LUNC-USDT"
    
    def test_hashtag_format(self):
        """Hashtag format should be extracted in BASE-USDT format."""
        assert extract_symbol(FREE_SIGNAL_ALT) == "BEAT-USDT"
    
    def test_direct_format(self):
        """Direct USDT format should be extracted in BASE-USDT format."""
        assert extract_symbol("Trade BTCUSDT now!") == "BTC-USDT"


class TestExtractDirection:
    """Tests for direction extraction."""
    
    def test_long_direction(self):
        """LONG direction should be extracted."""
        assert extract_direction(FREE_SIGNAL_EXAMPLE) == TradeDirection.LONG
    
    def test_short_direction(self):
        """SHORT direction should be extracted."""
        assert extract_direction(FREE_SIGNAL_SHORT) == TradeDirection.SHORT
    
    def test_with_emoji(self):
        """Direction with emoji should work."""
        assert extract_direction("LONG 📈") == TradeDirection.LONG
        assert extract_direction("SHORT 📉") == TradeDirection.SHORT


class TestExtractEntryPrice:
    """Tests for entry price extraction."""
    
    def test_range_entry(self):
        """Entry range should be extracted."""
        low, high = extract_entry_price(FREE_SIGNAL_EXAMPLE)
        assert low == 0.03950
        assert high == 0.04040
    
    def test_range_entry_short(self):
        """Entry range for short should be extracted."""
        low, high = extract_entry_price(FREE_SIGNAL_SHORT)
        assert low == 42500
        assert high == 42700
    
    def test_single_entry(self):
        """Single entry should be extracted."""
        text = "ENTRY: 0.5000"
        low, high = extract_entry_price(text)
        assert low == 0.5
        assert high is None


class TestExtractTakeProfits:
    """Tests for take profit extraction."""
    
    def test_numbered_tps(self):
        """Numbered TPs should be extracted."""
        tps = extract_take_profits(FREE_SIGNAL_EXAMPLE)
        assert len(tps) == 3
        assert 0.04150 in tps
        assert 0.04250 in tps
        assert 0.04400 in tps
    
    def test_tp_format(self):
        """TP format should be extracted."""
        text = "TP1: 100\nTP2: 110\nTP3: 120"
        tps = extract_take_profits(text)
        assert len(tps) == 3


class TestExtractStopLoss:
    """Tests for stop loss extraction."""
    
    def test_stop_loss(self):
        """Stop loss should be extracted."""
        sl = extract_stop_loss(FREE_SIGNAL_EXAMPLE)
        assert sl == 0.03860
    
    def test_sl_format(self):
        """SL format should be extracted."""
        text = "SL: 0.5000"
        assert extract_stop_loss(text) == 0.5
    
    def test_stop_loss_hold(self):
        """HOLD stop loss should return None."""
        text = "STOP LOSS: HOLD"
        assert extract_stop_loss(text) is None


class TestExtractLeverage:
    """Tests for leverage extraction."""
    
    def test_leverage_x(self):
        """Leverage with x should be extracted."""
        assert extract_leverage(FREE_SIGNAL_EXAMPLE) == 75
    
    def test_leverage_format(self):
        """Various leverage formats should work."""
        assert extract_leverage("LEVERAGE: 50x") == 50
        assert extract_leverage("50X LEVERAGE") == 50
        assert extract_leverage("Use 25× leverage") == 25


class TestParseFreeSignal:
    """Tests for complete signal parsing - returns BASE-USDT format symbols."""
    
    def test_parse_long_signal(self):
        """LONG signal should be parsed with BASE-USDT symbol format."""
        signal = parse_free_signal(FREE_SIGNAL_EXAMPLE)
        
        assert signal is not None
        assert signal.source == SignalSource.FREE
        assert signal.symbol == "1000LUNC-USDT"  # BASE-USDT format
        assert signal.direction == TradeDirection.LONG
        assert signal.entry_price_low == 0.03950
        assert signal.entry_price_high == 0.04040
        assert len(signal.take_profits) == 3
        assert signal.stop_loss == 0.03860
        assert signal.leverage == 75
    
    def test_parse_short_signal(self):
        """SHORT signal should be parsed with BASE-USDT symbol format."""
        signal = parse_free_signal(FREE_SIGNAL_SHORT)
        
        assert signal is not None
        assert signal.symbol == "BTC-USDT"  # BASE-USDT format
        assert signal.direction == TradeDirection.SHORT
    
    def test_parse_alt_format(self):
        """Alternative format should be parsed with BASE-USDT symbol format."""
        signal = parse_free_signal(FREE_SIGNAL_ALT)
        
        assert signal is not None
        assert signal.symbol == "BEAT-USDT"  # BASE-USDT format
        assert signal.direction == TradeDirection.LONG
    
    def test_parse_invalid(self):
        """Invalid text should return None."""
        signal = parse_free_signal("Hello world!")
        assert signal is None
    
    def test_parse_empty(self):
        """Empty text should return None."""
        signal = parse_free_signal("")
        assert signal is None
        
        signal = parse_free_signal(None)
        assert signal is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
