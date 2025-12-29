"""
Tests for image analyzer with FREE signal chart image support.
"""

import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import TradeDirection


class TestFreeSignalChartOCRExtractor:
    """Test FREE signal chart image OCR extraction."""
    
    @pytest.fixture
    def sample_ocr_text_full(self):
        """Sample OCR text with all fields."""
        return """
        🪙 COIN NAME: POWER(USDT)
        ✅ LEVERAGE: 75x
        📈 TRADE TYPE: LONG
        📉 ENTRY PRICE (0.3280-0.3200)
        
        TAKE-PROFITS
        1️⃣ 0.3350
        2️⃣ 0.3400
        3️⃣ 0.3460
        
        🤖 STOP LOSS: 0.3100
        """
    
    @pytest.fixture
    def sample_ocr_text_minimal(self):
        """Sample OCR text with minimal fields."""
        return """
        COIN NAME: BTCUSDT
        LONG
        ENTRY: 50000
        TP1: 51000
        SL: 49000
        """
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        from src.image_analyzer import FreeSignalChartOCRExtractor
        return FreeSignalChartOCRExtractor()
    
    def test_extract_symbol(self, extractor, sample_ocr_text_full):
        """Should extract symbol correctly in BASE-USDT format (BingX Swap V2 format)."""
        symbol = extractor.extract_symbol(sample_ocr_text_full)
        assert symbol == "POWER-USDT"  # BingX Swap V2 requires BASE-USDT format
    
    def test_extract_symbol_variants(self, extractor):
        """Should extract various symbol formats and normalize to BASE-USDT (BingX Swap V2 format)."""
        test_cases = [
            ("COIN NAME: 1000LUNC(USDT)", "1000LUNC-USDT"),  # BingX Swap V2 format
            ("COIN NAME: THE (USDT)", "THE-USDT"),
            ("#BEAT/USDT", "BEAT-USDT"),
            ("$ICNT some text", "ICNT-USDT"),
            ("BTCUSDT is trending", "BTC-USDT"),
        ]
        
        for text, expected in test_cases:
            symbol = extractor.extract_symbol(text)
            assert symbol == expected, f"Failed for input: {text}"
    
    def test_extract_direction(self, extractor, sample_ocr_text_full):
        """Should extract direction correctly."""
        direction = extractor.extract_direction(sample_ocr_text_full)
        assert direction == TradeDirection.LONG
    
    def test_extract_direction_short(self, extractor):
        """Should extract SHORT direction."""
        direction = extractor.extract_direction("TRADE TYPE: SHORT 📉")
        assert direction == TradeDirection.SHORT
    
    def test_extract_entry_price_range(self, extractor, sample_ocr_text_full):
        """Should extract entry price range."""
        low, high = extractor.extract_entry_price(sample_ocr_text_full)
        assert low == pytest.approx(0.3200, rel=0.01)
        assert high == pytest.approx(0.3280, rel=0.01)
    
    def test_extract_entry_price_single(self, extractor):
        """Should extract single entry price."""
        low, high = extractor.extract_entry_price("ENTRY PRICE: 0.5000")
        assert low == pytest.approx(0.5000, rel=0.01)
        assert high is None
    
    def test_extract_take_profits(self, extractor, sample_ocr_text_full):
        """Should extract take profit levels."""
        tps = extractor.extract_take_profits(sample_ocr_text_full)
        assert len(tps) == 3
        assert 0.3350 in tps
        assert 0.3400 in tps
        assert 0.3460 in tps
    
    def test_extract_stop_loss(self, extractor, sample_ocr_text_full):
        """Should extract stop loss."""
        sl = extractor.extract_stop_loss(sample_ocr_text_full)
        assert sl == pytest.approx(0.3100, rel=0.01)
    
    def test_extract_leverage(self, extractor, sample_ocr_text_full):
        """Should extract leverage."""
        leverage = extractor.extract_leverage(sample_ocr_text_full)
        assert leverage == 75
    
    def test_extract_leverage_variants(self, extractor):
        """Should extract various leverage formats."""
        test_cases = [
            ("LEVERAGE: 50x", 50),
            ("75X LEVERAGE", 75),
            ("100× leverage", 100),
            ("Leverage 25x", 25),
        ]
        
        for text, expected in test_cases:
            leverage = extractor.extract_leverage(text)
            assert leverage == expected, f"Failed for input: {text}"


class TestAnalyzeFreeSignalImage:
    """Test analyze_free_signal_image function."""
    
    @pytest.mark.asyncio
    async def test_analyze_returns_tp_sl(self):
        """Should return TP/SL from image analysis."""
        from src.image_analyzer import FreeSignalChartOCRExtractor, FreeSignalImageResult
        
        # Mock the OCR extraction
        with patch.object(FreeSignalChartOCRExtractor, 'extract_text') as mock_extract:
            mock_extract.return_value = """
            COIN NAME: BTCUSDT
            TRADE TYPE: LONG
            LEVERAGE: 50x
            ENTRY PRICE (50000-49500)
            1️⃣ 51000
            2️⃣ 52000
            STOP LOSS: 48000
            """
            
            from src.image_analyzer import analyze_free_signal_image
            
            # Create minimal mock image bytes
            from PIL import Image
            import io
            img = Image.new('RGB', (100, 100), color='white')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            result = await analyze_free_signal_image(img_bytes)
            
            assert result.is_valid is True
            assert result.symbol == "BTC-USDT"  # BingX Swap V2 requires BASE-USDT format
            assert result.direction == TradeDirection.LONG
            assert len(result.take_profits) >= 1
            assert result.stop_loss is not None


class TestImageAnalysisResultMerging:
    """Test that image results can be merged with text signals."""
    
    def test_free_signal_image_result_dataclass(self):
        """FreeSignalImageResult should work correctly."""
        from src.image_analyzer import FreeSignalImageResult
        
        result = FreeSignalImageResult(
            is_valid=True,
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            entry_price_low=49500.0,
            entry_price_high=50000.0,
            take_profits=[51000.0, 52000.0],
            stop_loss=48000.0,
            leverage=50,
        )
        
        assert result.is_valid is True
        assert result.symbol == "BTCUSDT"
        assert len(result.take_profits) == 2
        assert result.stop_loss == 48000.0
    
    def test_free_signal_image_result_default_take_profits(self):
        """take_profits should default to empty list."""
        from src.image_analyzer import FreeSignalImageResult
        
        result = FreeSignalImageResult(
            is_valid=False,
            error="Test error"
        )
        
        assert result.take_profits == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
