"""Property-based tests for reCAPTCHA service."""

import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import patch

from src.kene_api.recaptcha import RecaptchaService, RecaptchaVerificationResult


def create_recaptcha_service():
    """Create a reCAPTCHA service instance for testing."""
    with patch("src.kene_api.recaptcha.settings") as mock_settings:
        mock_settings.RECAPTCHA_SECRET_KEY = "test_secret_key"
        service = RecaptchaService()
        return service


class TestScoreValidation:
    """Property-based tests for score validation."""
    
    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        min_score=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_score_threshold_property(self, score, min_score):
        """Test that scores below threshold always fail and above always pass."""
        recaptcha_service = create_recaptcha_service()
        result = RecaptchaVerificationResult(
            success=True,
            score=score,
            action="test"
        )
        
        validated = recaptcha_service._validate_v3_response(result, "test", min_score)
        
        if score < min_score:
            assert not validated.success
            assert "score-too-low" in validated.error_codes
        else:
            assert validated.success
    
    @given(score=st.floats(min_value=0.0, max_value=1.0))
    def test_score_preservation(self, score):
        """Test that score value is preserved regardless of validation outcome."""
        recaptcha_service = create_recaptcha_service()
        result = RecaptchaVerificationResult(
            success=True,
            score=score,
            action="test"
        )
        
        # Test with threshold that might pass or fail
        validated = recaptcha_service._validate_v3_response(result, "test", 0.5)
        
        # Score should always be preserved
        assert validated.score == score
        
        # Success should depend on score vs threshold
        if score >= 0.5:
            assert validated.success
        else:
            assert not validated.success
    
    @given(
        score=st.floats(min_value=-100.0, max_value=100.0),
        min_score=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_invalid_scores_handled(self, score, min_score):
        """Test that invalid scores (outside 0-1 range) are handled."""
        # Only test scores outside valid range
        assume(score < 0.0 or score > 1.0)
        
        recaptcha_service = create_recaptcha_service()
        result = RecaptchaVerificationResult(
            success=True,
            score=score,
            action="test"
        )
        
        # Should handle gracefully without exceptions
        validated = recaptcha_service._validate_v3_response(result, "test", min_score)
        
        # Invalid scores should fail validation
        if score < 0.0 or score < min_score:
            assert not validated.success


class TestActionValidation:
    """Property-based tests for action validation."""
    
    @given(
        actual_action=st.text(min_size=1, max_size=50),
        expected_action=st.text(min_size=1, max_size=50)
    )
    def test_action_matching_property(self, actual_action, expected_action):
        """Test that action matching works correctly for any string."""
        recaptcha_service = create_recaptcha_service()
        result = RecaptchaVerificationResult(
            success=True,
            score=0.9,
            action=actual_action
        )
        
        validated = recaptcha_service._validate_v3_response(result, expected_action, 0.5)
        
        if actual_action == expected_action:
            assert validated.success
        else:
            assert not validated.success
            assert "action-mismatch" in validated.error_codes
    
    @given(action=st.text(min_size=1, max_size=50))
    def test_no_expected_action_always_passes(self, action):
        """Test that when no expected action is set, any action passes."""
        recaptcha_service = create_recaptcha_service()
        result = RecaptchaVerificationResult(
            success=True,
            score=0.9,
            action=action
        )
        
        # None or empty string for expected_action should always pass
        validated = recaptcha_service._validate_v3_response(result, None, 0.5)
        assert validated.success
        
        validated = recaptcha_service._validate_v3_response(result, "", 0.5)
        assert validated.success


class TestCombinedValidation:
    """Property-based tests for combined score and action validation."""
    
    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        min_score=st.floats(min_value=0.0, max_value=1.0),
        actual_action=st.text(min_size=1, max_size=20),
        expected_action=st.text(min_size=1, max_size=20)
    )
    def test_combined_validation_property(
        self, score, min_score, actual_action, expected_action
    ):
        """Test that both score and action must pass for success."""
        recaptcha_service = create_recaptcha_service()
        result = RecaptchaVerificationResult(
            success=True,
            score=score,
            action=actual_action
        )
        
        validated = recaptcha_service._validate_v3_response(result, expected_action, min_score)
        
        score_passes = score >= min_score
        action_passes = actual_action == expected_action
        
        if score_passes and action_passes:
            assert validated.success
        else:
            assert not validated.success
            # Check appropriate error codes
            if not score_passes:
                assert "score-too-low" in validated.error_codes
            elif not action_passes:
                assert "action-mismatch" in validated.error_codes
    
    @given(
        score=st.floats(min_value=0.0, max_value=1.0),
        min_score=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_score_preservation(self, score, min_score):
        """Test that score is always preserved in the result."""
        recaptcha_service = create_recaptcha_service()
        result = RecaptchaVerificationResult(
            success=True,
            score=score,
            action="test"
        )
        
        validated = recaptcha_service._validate_v3_response(result, "test", min_score)
        
        # Score should always be preserved regardless of validation result
        assert validated.score == score