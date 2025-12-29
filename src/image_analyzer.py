"""
Image analysis pipeline for Wolf Trading Bot.
Handles OCR extraction from Bitunix Pro screenshots AND FREE signal chart images.
"""

import re
import io
from typing import Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass

try:
    from PIL import Image
    import numpy as np
    import cv2
    import pytesseract
except ImportError as e:
    raise ImportError(
        f"Required image processing libraries not installed: {e}\n"
        "Install with: pip install pillow numpy opencv-python pytesseract"
    )

from .models import ImageAnalysisResult, TradeDirection
from .utils.logging_setup import get_logger
from .utils.symbol_utils import extract_symbol_from_various_formats, normalize_symbol

logger = get_logger(__name__)


@dataclass
class FreeSignalImageResult:
    """Result from OCR analysis of FREE signal chart image."""
    is_valid: bool
    symbol: Optional[str] = None
    direction: Optional[TradeDirection] = None
    entry_price_low: Optional[float] = None
    entry_price_high: Optional[float] = None
    take_profits: List[float] = None
    stop_loss: Optional[float] = None
    leverage: Optional[int] = None
    error: Optional[str] = None
    raw_ocr_text: str = ""
    
    def __post_init__(self):
        if self.take_profits is None:
            self.take_profits = []


class FreeSignalChartOCRExtractor:
    """
    OCR extractor optimized for FREE signal chart images (TradingView overlay).
    
    Expected image format:
    ┌─────────────────────────────────────────────────────────────────┐
    │ 🪙 COIN NAME: POWER(USDT)                                       │
    │ ✅ LEVERAGE: 75x                                                 │
    │ 📈 TRADE TYPE: LONG                                              │
    │ 📉 ENTRY PRICE (0.3280-0.3200)                                   │
    │ TAKE-PROFITS                                                     │
    │ 1️⃣ 0.3350                                                       │
    │ 2️⃣ 0.3400                                                       │
    │ 3️⃣ 0.3460                                                       │
    │ 🤖 STOP LOSS: 0.3100                                            │
    │ [TradingView Chart Background]                                   │
    └─────────────────────────────────────────────────────────────────┘
    """
    
    # Symbol patterns for FREE signals
    SYMBOL_PATTERNS = [
        r"COIN\s*NAME\s*[:\-]?\s*([A-Za-z0-9#_]+)\s*\(?([A-Za-z]*)\)?",
        r"#([A-Z0-9]+)\s*[\(/]?\s*(USDT?)\s*\)?",
        r"\b([A-Z0-9]{2,})(USDT)\b",
        r"\$([A-Z0-9]+)",
    ]
    
    # Direction patterns
    DIRECTION_PATTERNS = [
        r"TRADE\s*TYPE\s*[:\-]?\s*(LONG|SHORT)",
        r"DIRECTION\s*[:\-]?\s*(LONG|SHORT)",
        r"\b(LONG)\s*[📈🟢]",
        r"\b(SHORT)\s*[📉🔴]",
        r"🔼\s*TRADE\s*TYPE\s*[:\-]?\s*(LONG)",
        r"🔽\s*TRADE\s*TYPE\s*[:\-]?\s*(SHORT)",
        r"\b(LONG)\b",
        r"\b(SHORT)\b",
    ]
    
    # Entry price patterns (supports ranges)
    ENTRY_PATTERNS = [
        r"ENTRY\s*PRICE\s*\(?\s*([0-9]*\.?[0-9]+)\s*[-–—]\s*([0-9]*\.?[0-9]+)\s*\)?",
        r"ENTRY\s*[:\-]?\s*([0-9]*\.?[0-9]+)\s*[-–—]\s*([0-9]*\.?[0-9]+)",
        r"ENTRY\s*ZONE\s*[:\-]?\s*([0-9]*\.?[0-9]+)\s*[-–—]\s*([0-9]*\.?[0-9]+)",
        r"ENTRY\s*(?:PRICE)?\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
    ]
    
    # Take profit patterns
    TP_PATTERNS = [
        r"(?:[1-6]️⃣|[1-6]⃣)\s*([0-9]*\.?[0-9]+)",
        r"TP\s*[1-6]\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
        r"TAKE[\s\-]?PROFIT\s*[1-6]?\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
        r"TARGET\s*[1-6]\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
    ]
    
    # Stop loss patterns
    SL_PATTERNS = [
        r"(?:STOP\s*LOSS|STOPLOSS|SL)\s*[:\-]?\s*([0-9]*\.?[0-9]+)",
    ]
    
    # Leverage patterns
    LEVERAGE_PATTERNS = [
        r"LEVERAGE\s*[:\-]?\s*(\d+)\s*[xX×]?",
        r"(\d+)\s*[xX×]\s*LEVERAGE",
        r"\b(\d+)[xX×]\b",
    ]
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize the OCR extractor.
        
        Args:
            tesseract_cmd: Path to tesseract executable (for Windows)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def preprocess_image(self, image: Image.Image) -> List[Image.Image]:
        """
        Preprocess image for optimal OCR with multiple strategies.
        Returns multiple preprocessed versions for better results.
        """
        img_array = np.array(image)
        results = []
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Strategy 1: Direct thresholding (for dark background with light text)
        _, thresh1 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        results.append(Image.fromarray(thresh1))
        
        # Strategy 2: Invert + threshold (for light text on dark background)
        inverted = cv2.bitwise_not(gray)
        _, thresh2 = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(Image.fromarray(thresh2))
        
        # Strategy 3: CLAHE enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        results.append(Image.fromarray(enhanced))
        
        # Strategy 4: Bilateral filter + Otsu
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh4 = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results.append(Image.fromarray(thresh4))
        
        return results
    
    def extract_text(self, image: Image.Image) -> str:
        """
        Extract text from image using OCR with multiple preprocessing strategies.
        """
        all_text = []
        
        # Try original image
        try:
            text = pytesseract.image_to_string(image, config='--psm 6')
            all_text.append(text)
        except Exception as e:
            logger.warning(f"Original OCR failed: {e}")
        
        # Try different PSM modes on original
        for psm in [3, 4, 11]:
            try:
                text = pytesseract.image_to_string(image, config=f'--psm {psm}')
                all_text.append(text)
            except Exception:
                pass
        
        # Try preprocessed versions
        try:
            preprocessed_images = self.preprocess_image(image)
            for pp_img in preprocessed_images:
                try:
                    text = pytesseract.image_to_string(pp_img, config='--psm 6')
                    all_text.append(text)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}")
        
        # Combine all results
        combined = "\n".join(all_text)
        logger.debug(f"OCR raw text (first 1000 chars): {combined[:1000]}...")
        
        return combined
    
    def extract_symbol(self, text: str) -> Optional[str]:
        """Extract trading symbol from OCR text using shared utility."""
        return extract_symbol_from_various_formats(text)
    
    def extract_direction(self, text: str) -> Optional[TradeDirection]:
        """Extract trade direction from OCR text."""
        for pattern in self.DIRECTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                direction_str = match.group(1).upper()
                logger.debug(f"Extracted direction: {direction_str}")
                return TradeDirection.LONG if direction_str == "LONG" else TradeDirection.SHORT
        return None
    
    def extract_entry_price(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """Extract entry price(s) from OCR text."""
        for pattern in self.ENTRY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if match.lastindex >= 2:
                        price1 = float(match.group(1))
                        price2 = float(match.group(2))
                        entry_low = min(price1, price2)
                        entry_high = max(price1, price2)
                        logger.debug(f"Extracted entry range: {entry_low} - {entry_high}")
                        return entry_low, entry_high
                    else:
                        price = float(match.group(1))
                        logger.debug(f"Extracted single entry: {price}")
                        return price, None
                except (ValueError, IndexError):
                    continue
        return None, None
    
    def extract_take_profits(self, text: str) -> List[float]:
        """Extract take profit levels from OCR text."""
        tps = []
        for pattern in self.TP_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    tp = float(match)
                    if tp not in tps and tp > 0:
                        tps.append(tp)
                except ValueError:
                    continue
        tps.sort()
        logger.debug(f"Extracted TPs: {tps}")
        return tps
    
    def extract_stop_loss(self, text: str) -> Optional[float]:
        """Extract stop loss from OCR text."""
        for pattern in self.SL_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    sl = float(match.group(1))
                    if sl > 0:
                        logger.debug(f"Extracted SL: {sl}")
                        return sl
                except ValueError:
                    continue
        return None
    
    def extract_leverage(self, text: str) -> Optional[int]:
        """Extract leverage from OCR text."""
        for pattern in self.LEVERAGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    leverage = int(match.group(1))
                    if 1 <= leverage <= 200:
                        logger.debug(f"Extracted leverage: {leverage}x")
                        return leverage
                except ValueError:
                    continue
        return None
    
    def analyze(self, image_data: bytes) -> FreeSignalImageResult:
        """
        Analyze FREE signal chart image and extract trading data including TP/SL.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            FreeSignalImageResult with extracted data
        """
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            logger.debug(f"Image loaded: {image.size}, mode: {image.mode}")
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract text via OCR
            ocr_text = self.extract_text(image)
            
            if not ocr_text.strip():
                return FreeSignalImageResult(
                    is_valid=False,
                    error="OCR returned empty text",
                    raw_ocr_text=""
                )
            
            # Parse the text
            symbol = self.extract_symbol(ocr_text)
            direction = self.extract_direction(ocr_text)
            entry_low, entry_high = self.extract_entry_price(ocr_text)
            take_profits = self.extract_take_profits(ocr_text)
            stop_loss = self.extract_stop_loss(ocr_text)
            leverage = self.extract_leverage(ocr_text)
            
            # Check if we have at least TP/SL (the main value from images)
            has_tp_sl = bool(take_profits or stop_loss)
            
            return FreeSignalImageResult(
                is_valid=has_tp_sl,  # Valid if we found TP or SL
                symbol=symbol,
                direction=direction,
                entry_price_low=entry_low,
                entry_price_high=entry_high,
                take_profits=take_profits if take_profits else [],
                stop_loss=stop_loss,
                leverage=leverage,
                raw_ocr_text=ocr_text
            )
            
        except Exception as e:
            logger.exception("FREE signal image analysis failed")
            return FreeSignalImageResult(
                is_valid=False,
                error=str(e),
                raw_ocr_text=""
            )


class BitunixProOCRExtractor:
    """
    OCR extractor optimized for Bitunix Pro screenshots (VIP signals).
    
    Expected image format:
    ┌─────────────────────────────────────────────────────────────────┐
    │ 📱 Bitunix Pro (logo)                                           │
    ├─────────────────────────────────────────────────────────────────┤
    │   ICNTUSDT | Long 50X        ← PARSE THIS LINE                  │
    │   +147.52%                   ← PROFIT (if shown)                │
    │   Entry Price  0.4623        ← ENTRY PRICE                      │
    │   Last Price   0.4760        ← CURRENT PRICE                    │
    └─────────────────────────────────────────────────────────────────┘
    """
    
    # Main header pattern: "SYMBOLUSDT | Long/Short XXx"
    HEADER_PATTERN = r'([A-Z0-9]+USDT)\s*[|｜\|]\s*(Long|Short)\s*(\d+)\s*[Xx×]?'
    
    # Alternative patterns with OCR error tolerance
    SYMBOL_PATTERNS = [
        r'([A-Z0-9]{3,}USDT)',
        r'([A-Z0-9]{3,})USDT',
    ]
    
    # Direction patterns with OCR error tolerance
    DIRECTION_PATTERNS = [
        r'\b(L[O0]NG)\b',    # LONG or L0NG (zero instead of O)
        r'\b(SH[O0]RT)\b',   # SHORT or SH0RT
        r'\b(Long)\b',
        r'\b(Short)\b',
    ]
    
    # Price patterns
    ENTRY_PRICE_PATTERN = r'Entry\s*Price\s*[:\s]*([0-9]+\.?[0-9]*)'
    LAST_PRICE_PATTERN = r'Last\s*Price\s*[:\s]*([0-9]+\.?[0-9]*)'
    
    # Leverage patterns
    LEVERAGE_PATTERNS = [
        r'(\d+)\s*[Xx×]',
        r'[Xx×]\s*(\d+)',
    ]
    
    # Profit pattern
    PROFIT_PATTERN = r'([+-]?\d+\.?\d*)\s*%'
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize the OCR extractor.
        
        Args:
            tesseract_cmd: Path to tesseract executable (for Windows)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for optimal OCR.
        Dark background with white/green text → inverted for better OCR.
        """
        # Convert to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Invert colors (dark → light for better OCR)
        inverted = cv2.bitwise_not(gray)
        
        # Apply bilateral filter for noise reduction while keeping edges
        filtered = cv2.bilateralFilter(inverted, 9, 75, 75)
        
        # Apply CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(filtered)
        
        # Apply Otsu's thresholding
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return Image.fromarray(binary)
    
    def extract_text(self, image: Image.Image) -> str:
        """
        Extract text from image using OCR.
        Tries multiple preprocessing approaches.
        """
        results = []
        
        # Try with preprocessing
        try:
            preprocessed = self.preprocess_image(image)
            text1 = pytesseract.image_to_string(preprocessed, config='--psm 6')
            results.append(text1)
        except Exception as e:
            logger.warning(f"Preprocessed OCR failed: {e}")
        
        # Try without preprocessing (original image)
        try:
            text2 = pytesseract.image_to_string(image, config='--psm 6')
            results.append(text2)
        except Exception as e:
            logger.warning(f"Original OCR failed: {e}")
        
        # Try with different PSM mode
        try:
            text3 = pytesseract.image_to_string(image, config='--psm 4')
            results.append(text3)
        except Exception as e:
            logger.warning(f"PSM 4 OCR failed: {e}")
        
        # Combine results (use longest or most complete)
        combined = "\n".join(results)
        logger.debug(f"OCR raw text: {combined[:500]}...")
        
        return combined
    
    def parse_ocr_text(self, ocr_text: str) -> dict:
        """
        Parse extracted OCR text to find trading data.
        OCR USAGE RULE: For VIP signals, ONLY extract direction.
        Symbol MUST come from caption text, never OCR.
        """
        result = {
            'symbol': None,  # NEVER extract symbol from OCR for VIP signals
            'direction': None,
            'entry_price': None,
            'last_price': None,
            'leverage': None,
            'profit_percent': None,
        }
        
        # Normalize text (uppercase for matching)
        text_upper = ocr_text.upper()
        
        # VIP OCR RULE: Only extract direction, never symbol
        # Symbol must come from caption text to prevent corruption
        for pattern in self.DIRECTION_PATTERNS:
            match = re.search(pattern, text_upper)
            if match:
                direction_str = match.group(1).upper().replace('0', 'O')
                result['direction'] = TradeDirection.LONG if 'LONG' in direction_str else TradeDirection.SHORT
                logger.debug(f"VIP OCR extracted direction: {result['direction']}")
                break
        
        # Extract leverage (optional, for reference only)
        for pattern in self.LEVERAGE_PATTERNS:
            match = re.search(pattern, text_upper)
            if match:
                try:
                    result['leverage'] = int(match.group(1))
                except ValueError:
                    pass
                break
        
        # Extract entry price (optional, for reference only)
        entry_match = re.search(self.ENTRY_PRICE_PATTERN, ocr_text, re.IGNORECASE)
        if entry_match:
            try:
                result['entry_price'] = float(entry_match.group(1))
                logger.debug(f"Entry price (reference): {result['entry_price']}")
            except ValueError:
                pass
        
        # Extract last price (optional, for reference only)
        last_match = re.search(self.LAST_PRICE_PATTERN, ocr_text, re.IGNORECASE)
        if last_match:
            try:
                result['last_price'] = float(last_match.group(1))
                logger.debug(f"Last price (reference): {result['last_price']}")
            except ValueError:
                pass
        
        # Extract profit percentage (optional, for reference only)
        profit_match = re.search(self.PROFIT_PATTERN, ocr_text)
        if profit_match:
            try:
                result['profit_percent'] = float(profit_match.group(1))
            except ValueError:
                pass
        
        return result
    
    def analyze(self, image_data: bytes) -> ImageAnalysisResult:
        """
        Analyze VIP signal image and extract trading data.
        OCR USAGE RULE: Only extract direction for VIP signals.
        Symbol must come from caption text.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            ImageAnalysisResult with extracted data
        """
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            logger.debug(f"Image loaded: {image.size}, mode: {image.mode}")
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract text via OCR
            ocr_text = self.extract_text(image)
            
            if not ocr_text.strip():
                return ImageAnalysisResult(
                    is_valid=False,
                    error="OCR returned empty text",
                    raw_ocr_text=""
                )
            
            # Parse the text (only direction for VIP signals)
            parsed = self.parse_ocr_text(ocr_text)
            
            # OCR FAILURE HANDLING: Must confidently detect EXACTLY ONE direction
            if not parsed['direction']:
                return ImageAnalysisResult(
                    is_valid=False,
                    error="OCR failed to detect direction (LONG/SHORT) - trade skipped safely",
                    raw_ocr_text=ocr_text
                )
            
            # Symbol is NOT extracted from OCR - must come from caption
            # This prevents OCR corruption of symbols
            return ImageAnalysisResult(
                is_valid=True,
                symbol=None,  # Must be provided by caption parser
                direction=parsed['direction'],
                entry_price=parsed['entry_price'],  # Reference only
                last_price=parsed['last_price'],    # Reference only
                leverage=parsed['leverage'],        # Reference only
                profit_percent=parsed['profit_percent'],  # Reference only
                platform="Bitunix Pro",
                raw_ocr_text=ocr_text
            )
            
        except Exception as e:
            logger.exception("VIP image analysis failed")
            return ImageAnalysisResult(
                is_valid=False,
                error=str(e),
                raw_ocr_text=""
            )


# Global extractor instances
_vip_extractor: Optional[BitunixProOCRExtractor] = None
_free_extractor: Optional[FreeSignalChartOCRExtractor] = None


def get_vip_extractor(tesseract_cmd: Optional[str] = None) -> BitunixProOCRExtractor:
    """Get or create the global VIP OCR extractor instance."""
    global _vip_extractor
    if _vip_extractor is None:
        _vip_extractor = BitunixProOCRExtractor(tesseract_cmd)
    return _vip_extractor


def get_free_extractor(tesseract_cmd: Optional[str] = None) -> FreeSignalChartOCRExtractor:
    """Get or create the global FREE signal OCR extractor instance."""
    global _free_extractor
    if _free_extractor is None:
        _free_extractor = FreeSignalChartOCRExtractor(tesseract_cmd)
    return _free_extractor


# Legacy alias for backward compatibility
def get_extractor(tesseract_cmd: Optional[str] = None) -> BitunixProOCRExtractor:
    """Legacy function - returns VIP extractor for backward compatibility."""
    return get_vip_extractor(tesseract_cmd)


async def analyze_vip_signal_image(
    image_data: bytes,
    caption: str = "",
    tesseract_cmd: Optional[str] = None
) -> ImageAnalysisResult:
    """
    Analyze a VIP signal image following strict OCR usage rules.
    
    PROCESSING PRIORITY ORDER:
    1) Telegram message structure (already verified by classifier)
    2) Caption text parsing (symbol extraction)
    3) OCR (direction extraction only)
    
    OCR USAGE RULES:
    - OCR is REQUIRED ONLY for extracting trade direction
    - Symbol MUST ALWAYS be extracted from caption text
    - OCR MUST NEVER be used to extract or override the symbol
    
    Args:
        image_data: Raw image bytes
        caption: Caption text for symbol extraction (REQUIRED)
        tesseract_cmd: Path to tesseract executable
        
    Returns:
        ImageAnalysisResult with extracted data
    """
    # Step 1: Extract symbol from caption text (NEVER from OCR)
    from .free_signal_parser import extract_symbol
    
    symbol = extract_symbol(caption)
    if not symbol:
        return ImageAnalysisResult(
            is_valid=False,
            error="Symbol extraction failed from caption - OCR cannot override",
            raw_ocr_text=""
        )
    
    # Step 2: Use OCR to extract direction ONLY
    extractor = get_vip_extractor(tesseract_cmd)
    result = extractor.analyze(image_data)
    
    # Step 3: Combine results following strict rules
    if result.is_valid:
        # Override symbol with caption-derived symbol (never OCR symbol)
        result.symbol = symbol
        result.platform = "Bitunix Pro (Caption symbol + OCR direction)"
        logger.info(f"VIP signal analysis complete: {symbol} {result.direction.value}")
    else:
        # OCR failed to extract direction - fail safely
        logger.error(f"VIP OCR failed for {symbol}: {result.error}")
        result.error = f"OCR direction extraction failed for {symbol}: {result.error}"
    
    return result


async def analyze_free_signal_image(
    image_data: bytes,
    tesseract_cmd: Optional[str] = None
) -> FreeSignalImageResult:
    """
    Analyze a FREE signal chart image and extract trading data including TP/SL.
    
    Args:
        image_data: Raw image bytes
        tesseract_cmd: Path to tesseract executable
        
    Returns:
        FreeSignalImageResult with extracted TP/SL data
    """
    extractor = get_free_extractor(tesseract_cmd)
    return extractor.analyze(image_data)
