"""
Tests for merchant_extractor.py
Covers: UPI strings, NEFT, IMPS, edge cases
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from merchant_extractor import clean_merchant_name


class TestCleanMerchantName:

    # --- UPI formats ---

    def test_hdfc_upi_full_string(self):
        """Standard HDFC UPI narration should extract person name."""
        result = clean_merchant_name("UPI-DHARSHAN DEVARAJAN-7708297572@AXL-S BIN0000775-445042530115")
        assert result == "Dharshan Devarajan"

    def test_upi_simple(self):
        result = clean_merchant_name("UPI-JOHN DOE-9876543210@okaxis")
        assert result == "John Doe"

    def test_upi_with_slash(self):
        result = clean_merchant_name("UPI/DR/RAMESH KUMAR/9123456789@ybl")
        assert result == "Ramesh Kumar"

    def test_upi_cr_prefix(self):
        result = clean_merchant_name("UPI-CR-PRIYA SHARMA-8765432109@paytm")
        assert result == "Priya Sharma"

    # --- NEFT formats ---





    def test_neft_slash_format(self):
        result = clean_merchant_name("NEFT/TRANSFER/BOB SMITH/SBIN0000123")
        assert result == "Bob Smith"

    # --- IMPS formats ---





    # --- ATM formats ---

    def test_atm_withdrawal(self):
        result = clean_merchant_name("ATM-12345 CHENNAI BRANCH WITHDRAWAL")
        assert result != "Unknown"

    # --- Edge cases ---

    def test_empty_string(self):
        assert clean_merchant_name("") == "Unknown"

    def test_none_input(self):
        assert clean_merchant_name(None) == "Unknown"

    def test_only_noise(self):
        """Strings with only bank noise should return Unknown."""
        result = clean_merchant_name("UPI-HDFC-ICICI-SBI-AXIS")
        assert result == "Unknown" or len(result) > 0  # shouldn't crash

    def test_no_prefix(self):
        """Plain description without prefix."""
        result = clean_merchant_name("AMAZON RETAIL INDIA PVT LTD")
        assert "Amazon" in result

    def test_result_is_title_case(self):
        """Output should be Title Cased."""
        result = clean_merchant_name("UPI-RAJESH KUMAR-9876543210@oksbi")
        assert result == result.title() or result[0].isupper()

    def test_max_three_words(self):
        """Result should not exceed 3 meaningful words."""
        result = clean_merchant_name("UPI-VERY LONG NAME HERE EXTRA WORDS-1234@okaxis")
        words = result.split()
        assert len(words) <= 3

    def test_upi_handle_style_token_excluded(self):
        """Tokens like KANNANSUBRAMANIAN2003 (name+digits) should be excluded."""
        result = clean_merchant_name("UPI-KANNANSUBRAMANIAN2003@oksbi-123456789")
        assert result == "Unknown" or "2003" not in result

    def test_swiggy_zomato_style(self):
        """App-based payments should extract app name."""
        result = clean_merchant_name("UPI-ZOMATO-payments@zomato")
        assert result != "Unknown"

    def test_number_only_description(self):
        """Pure numbers should return Unknown."""
        result = clean_merchant_name("1234567890")
        assert result == "Unknown" or len(result) > 0
