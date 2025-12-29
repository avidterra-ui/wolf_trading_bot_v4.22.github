"""
Tests for message classifier.
"""

import pytest
from unittest.mock import MagicMock, Mock

import sys
sys.path.insert(0, str(__file__).rsplit('/tests', 1)[0])

from src.message_classifier import (
    is_results_post,
    has_required_signal_fields,
    is_first_vip_signal,
    classify_message,
    SignalType,
)
from tests.fixtures.sample_messages import (
    FREE_SIGNAL_EXAMPLE,
    FREE_SIGNAL_SHORT,
    VIP_SIGNAL_CAPTION,
    VIP_SIGNAL_FIRST_POST,
    RESULTS_POST,
    PROMO_POST,
    INVALID_MESSAGE,
    NOT_A_SIGNAL,
)


class TestIsResultsPost:
    """Tests for results post detection."""
    
    def test_results_post_detected(self):
        """Results post should be detected."""
        assert is_results_post(RESULTS_POST) == True
    
    def test_vip_result_caption_detected(self):
        """VIP result caption should be detected as results."""
        assert is_results_post(VIP_SIGNAL_CAPTION) == True
    
    def test_promo_post_detected(self):
        """Promotional post should be detected."""
        # Promo posts may or may not be results - depends on content
        # This one doesn't have result indicators
        assert is_results_post(PROMO_POST) == False
    
    def test_free_signal_not_results(self):
        """Free signal should not be detected as results."""
        assert is_results_post(FREE_SIGNAL_EXAMPLE) == False
    
    def test_empty_text(self):
        """Empty text should not be results."""
        assert is_results_post("") == False
        assert is_results_post(None) == False


class TestHasRequiredFields:
    """Tests for required signal fields detection."""
    
    def test_free_signal_has_fields(self):
        """Free signal should have required fields."""
        assert has_required_signal_fields(FREE_SIGNAL_EXAMPLE) == True
    
    def test_free_signal_short_has_fields(self):
        """Short signal should have required fields."""
        assert has_required_signal_fields(FREE_SIGNAL_SHORT) == True
    
    def test_invalid_message_no_fields(self):
        """Invalid message should not have required fields."""
        assert has_required_signal_fields(INVALID_MESSAGE) == False
    
    def test_not_a_signal(self):
        """Text with keywords but not a signal should fail."""
        # This might pass some checks but should fail overall
        # because it doesn't have proper structure
        assert has_required_signal_fields(NOT_A_SIGNAL) == False


class TestIsFirstVIPSignal:
    """Tests for first VIP signal detection."""
    
    def test_first_post_is_first(self):
        """First post without result indicators should be first."""
        message = MagicMock()
        message.reply_to = None
        message.text = VIP_SIGNAL_FIRST_POST
        message.message = VIP_SIGNAL_FIRST_POST
        
        assert is_first_vip_signal(message) == True
    
    def test_result_post_not_first(self):
        """Result post should still be first signal (text checking removed)."""
        message = MagicMock()
        message.reply_to = None
        message.text = VIP_SIGNAL_CAPTION
        message.message = VIP_SIGNAL_CAPTION
        
        # Updated: Text checking removed - only reply_to matters now
        assert is_first_vip_signal(message) == True
    
    def test_reply_not_first(self):
        """Reply should not be first signal."""
        message = MagicMock()
        message.reply_to = MagicMock()  # Has reply_to
        message.text = "Some text"
        message.message = "Some text"
        
        assert is_first_vip_signal(message) == False


class TestClassifyMessage:
    """Tests for message classification."""
    
    def create_mock_message(self, text, is_forward=False, has_photo=False, has_reply=False):
        """Create a mock Telegram message."""
        message = MagicMock()
        message.text = text
        message.message = text
        message.caption = text  # Set caption to text for testing
        message.reply_to = MagicMock() if has_reply else None
        message.photo = MagicMock() if has_photo else None
        
        if is_forward:
            message.forward = MagicMock()
            message.forward.chat = MagicMock()
            message.forward.chat.title = "WOLF OFFICIAL VIP"
        else:
            message.forward = None
        
        return message
    
    def test_free_signal_classified(self):
        """Free signal should be classified correctly."""
        message = self.create_mock_message(FREE_SIGNAL_EXAMPLE)
        signal_type, reason = classify_message(message)
        assert signal_type == SignalType.FREE_SIGNAL
    
    def test_vip_signal_with_photo_classified(self):
        """VIP signal with photo should be classified."""
        message = self.create_mock_message(
            VIP_SIGNAL_FIRST_POST,
            is_forward=True,
            has_photo=True
        )
        signal_type, reason = classify_message(message)
        assert signal_type == SignalType.VIP_SIGNAL
    
    def test_vip_forward_without_photo_promotional(self):
        """VIP forward without photo should still be VIP_SIGNAL (photo requirement removed)."""
        message = self.create_mock_message(
            VIP_SIGNAL_FIRST_POST,
            is_forward=True,
            has_photo=False
        )
        signal_type, reason = classify_message(message)
        # Updated: Photo requirement removed - still VIP_SIGNAL if forwarded from VIP
        assert signal_type == SignalType.VIP_SIGNAL
    
    def test_vip_result_ignored(self):
        """VIP result should still be VIP_SIGNAL (text checking removed)."""
        message = self.create_mock_message(
            VIP_SIGNAL_CAPTION,
            is_forward=True,
            has_photo=True
        )
        signal_type, reason = classify_message(message)
        # Updated: Text content checking removed - still VIP_SIGNAL if forwarded from VIP
        assert signal_type == SignalType.VIP_SIGNAL
    
    def test_results_post_promotional(self):
        """Results post should be unknown (not forwarded, missing required fields)."""
        message = self.create_mock_message(RESULTS_POST)
        signal_type, reason = classify_message(message)
        # Updated: Results posts don't have required FREE signal fields (symbol, direction, entry, stop loss)
        assert signal_type == SignalType.UNKNOWN
    
    def test_invalid_message_unknown(self):
        """Invalid message should be unknown."""
        message = self.create_mock_message(INVALID_MESSAGE)
        signal_type, reason = classify_message(message)
        assert signal_type == SignalType.UNKNOWN
    
    def test_vip_disabled(self):
        """VIP signal should be unknown when disabled."""
        message = self.create_mock_message(
            VIP_SIGNAL_FIRST_POST,
            is_forward=True,
            has_photo=True
        )
        signal_type, reason = classify_message(message, enable_vip=False)
        assert signal_type == SignalType.UNKNOWN
    
    def test_free_disabled(self):
        """Free signal should be unknown when disabled."""
        message = self.create_mock_message(FREE_SIGNAL_EXAMPLE)
        signal_type, reason = classify_message(message, enable_free=False)
        assert signal_type == SignalType.UNKNOWN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
