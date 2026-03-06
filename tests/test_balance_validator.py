"""
Tests for balance_validator.py
Covers: clean amount parsing, balance fill, progression validation
"""

import pytest
import pandas as pd
import sys
import os

# Allow importing from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from balance_validator import validate_and_correct, _clean_amount


# ===========================================================================
# _clean_amount tests
# ===========================================================================

class TestCleanAmount:

    def test_plain_number(self):
        assert _clean_amount("1000.00") == 1000.0

    def test_with_rupee_symbol(self):
        assert _clean_amount("₹1,500.00") == 1500.0

    def test_with_commas(self):
        assert _clean_amount("1,00,000.00") == 100000.0

    def test_with_dr_suffix(self):
        assert _clean_amount("500.00 DR") == 500.0

    def test_with_cr_suffix(self):
        assert _clean_amount("750.00 CR") == 750.0

    def test_negative_becomes_positive(self):
        assert _clean_amount("-200.00") == 200.0

    def test_empty_string(self):
        assert _clean_amount("") == 0.0

    def test_none_value(self):
        assert _clean_amount(None) == 0.0

    def test_nan_string(self):
        assert _clean_amount("nan") == 0.0

    def test_none_string(self):
        assert _clean_amount("none") == 0.0

    def test_dollar_symbol(self):
        assert _clean_amount("$250.50") == 250.5

    def test_whitespace_only(self):
        assert _clean_amount("   ") == 0.0

    def test_integer_string(self):
        assert _clean_amount("5000") == 5000.0

    def test_invalid_text(self):
        assert _clean_amount("ABCXYZ") == 0.0


# ===========================================================================
# validate_and_correct tests
# ===========================================================================

class TestValidateAndCorrect:

    def _make_df(self, rows):
        """Helper to create a standard DataFrame."""
        return pd.DataFrame(rows, columns=["date", "description", "debit", "credit", "balance"])

    def test_valid_progression_flags_all_true(self):
        """A correct debit/credit/balance sequence should all pass."""
        df = self._make_df([
            ["2024-01-01", "Opening",  0.0,    0.0,    10000.0],
            ["2024-01-02", "Groceries",500.0,  0.0,    9500.0],
            ["2024-01-03", "Salary",   0.0,    5000.0, 14500.0],
        ])
        result = validate_and_correct(df)
        assert result["_balance_valid"].all(), "All rows should be valid"

    def test_invalid_balance_flagged(self):
        """A row with wrong balance should be flagged False."""
        df = self._make_df([
            ["2024-01-01", "Start",     0.0,   0.0,   10000.0],
            ["2024-01-02", "Debit",  1000.0,   0.0,   8000.0],   # wrong: should be 9000
        ])
        result = validate_and_correct(df)
        assert result["_balance_valid"].iloc[1] == False

    def test_missing_balance_filled_by_ffill(self):
        """Zero balances should be forward-filled from previous row."""
        df = self._make_df([
            ["2024-01-01", "Start",  0.0, 0.0, 10000.0],
            ["2024-01-02", "Txn",    500.0, 0.0, 0.0],  # missing balance
        ])
        result = validate_and_correct(df)
        assert result["balance"].iloc[1] == 10000.0  # filled from previous

    def test_no_negative_debits(self):
        """Negative debits should be clipped to 0."""
        df = self._make_df([
            ["2024-01-01", "Weird", -500.0, 0.0, 10000.0],
        ])
        result = validate_and_correct(df)
        assert result["debit"].iloc[0] >= 0

    def test_no_negative_credits(self):
        """Negative credits should be clipped to 0."""
        df = self._make_df([
            ["2024-01-01", "Weird", 0.0, -300.0, 10000.0],
        ])
        result = validate_and_correct(df)
        assert result["credit"].iloc[0] >= 0

    def test_single_row_no_crash(self):
        """Single row DataFrame should not crash."""
        df = self._make_df([
            ["2024-01-01", "Solo", 0.0, 0.0, 5000.0],
        ])
        result = validate_and_correct(df)
        assert len(result) == 1

    def test_empty_df_no_crash(self):
        """Empty DataFrame should return empty without error."""
        df = self._make_df([])
        result = validate_and_correct(df)
        assert result.empty

    def test_tolerance_within_one_rupee(self):
        """Balance off by ₹0.50 (rounding) should still pass."""
        df = self._make_df([
            ["2024-01-01", "Start",   0.0,    0.0,    10000.00],
            ["2024-01-02", "Txn",   500.0,    0.0,    9499.50],  # ₹0.50 off — within tolerance
        ])
        result = validate_and_correct(df)
        assert result["_balance_valid"].iloc[1] == True

    def test_rupee_symbol_in_balance(self):
        """Balance column with ₹ symbols should be cleaned properly.
        Note: debit/credit must be numeric — only balance is string here."""
        df = self._make_df([
            ["2024-01-01", "Start", 0.0, 0.0, "₹10,000.00"],
            ["2024-01-02", "Debit", 500.0, 0.0, "₹9,500.00"],
        ])
        result = validate_and_correct(df)
        assert result["balance"].iloc[0] == 10000.0
        assert result["balance"].iloc[1] == 9500.0
