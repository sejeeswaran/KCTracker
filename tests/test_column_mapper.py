"""
Tests for column_mapper.py
Covers: header mapping, DR/CR splitting, fallback detection
"""

import pytest
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from column_mapper import map_columns, _resolve_column_name, _clean_amount, _detect_dr_cr


# ===========================================================================
# _resolve_column_name tests
# ===========================================================================

class TestResolveColumnName:

    def test_exact_match_date(self):
        assert _resolve_column_name("date") == "date"

    def test_exact_match_narration(self):
        assert _resolve_column_name("narration") == "description"

    def test_exact_match_withdrawal(self):
        assert _resolve_column_name("withdrawal") == "debit"

    def test_exact_match_deposit(self):
        assert _resolve_column_name("deposit") == "credit"

    def test_exact_match_closing_balance(self):
        assert _resolve_column_name("closing balance") == "balance"

    def test_case_insensitive(self):
        assert _resolve_column_name("NARRATION") == "description"
        assert _resolve_column_name("Date") == "date"

    def test_partial_match(self):
        assert _resolve_column_name("withdrawal amt") == "debit"

    def test_unknown_column_returns_none(self):
        assert _resolve_column_name("random_xyz_col") is None

    def test_newline_in_column_name(self):
        # PDFs sometimes have newlines in headers
        assert _resolve_column_name("withdrawal\namt") == "debit"


# ===========================================================================
# _detect_dr_cr tests
# ===========================================================================

class TestDetectDrCr:

    def test_detects_dr(self):
        assert _detect_dr_cr("500.00DR") == "DR"

    def test_detects_cr(self):
        assert _detect_dr_cr("750.00CR") == "CR"

    def test_detects_lowercase_dr(self):
        assert _detect_dr_cr("500.00dr") == "DR"

    def test_detects_lowercase_cr(self):
        assert _detect_dr_cr("750.00cr") == "CR"

    def test_no_suffix_returns_none(self):
        assert _detect_dr_cr("500.00") is None

    def test_empty_returns_none(self):
        assert _detect_dr_cr("") is None

    def test_none_returns_none(self):
        assert _detect_dr_cr(None) is None


# ===========================================================================
# map_columns tests
# ===========================================================================

class TestMapColumns:

    def test_standard_hdfc_headers(self):
        """Maps standard HDFC-style headers correctly."""
        df = pd.DataFrame([
            ["01/01/2024", "Zomato UPI", "500.00", "", "9500.00"]
        ], columns=["Date", "Narration", "Withdrawal Amt", "Deposit Amt", "Closing Balance"])

        result = map_columns(df)
        assert "date" in result.columns
        assert "description" in result.columns
        assert "debit" in result.columns
        assert "credit" in result.columns
        assert "balance" in result.columns

    def test_all_required_columns_always_present(self):
        """Even with bad headers, all 5 required columns must appear."""
        df = pd.DataFrame([
            ["01/01/2024", "Some txn", "100", "0", "5000"]
        ], columns=["col1", "col2", "col3", "col4", "col5"])

        result = map_columns(df)
        for col in ["date", "description", "debit", "credit", "balance"]:
            assert col in result.columns, f"Missing required column: {col}"

    def test_single_amount_column_split(self):
        """Single amount column with DR/CR suffix should split into debit/credit."""
        df = pd.DataFrame([
            ["01/01/2024", "Groceries", "500.00DR", "9500.00"],
            ["02/01/2024", "Salary",    "5000.00CR", "14500.00"],
        ], columns=["date", "description", "amount", "balance"])

        result = map_columns(df)
        assert "debit" in result.columns
        assert "credit" in result.columns
        # Grocery row should have debit
        assert float(result["debit"].iloc[0]) == 500.0
        assert float(result["credit"].iloc[0]) == 0.0
        # Salary row should have credit
        assert float(result["debit"].iloc[1]) == 0.0
        assert float(result["credit"].iloc[1]) == 5000.0

    def test_drops_helper_columns(self):
        """Helper columns like time, type, ref should be removed after mapping."""
        df = pd.DataFrame([
            ["01/01/2024", "10:30", "Zomato", "500", "", "9500", "REF123", "DR"]
        ], columns=["date", "time", "description", "debit", "credit", "balance", "ref", "type"])

        result = map_columns(df)
        assert "time" not in result.columns
        assert "type" not in result.columns
        assert "ref" not in result.columns

    def test_empty_df_no_crash(self):
        """Empty DataFrame should not crash."""
        df = pd.DataFrame(columns=["date", "narration", "debit", "credit", "balance"])
        result = map_columns(df)
        assert result is not None

    def test_case_insensitive_headers(self):
        """Column headers in any case should be mapped."""
        df = pd.DataFrame([
            ["01/01/2024", "UPI transfer", "200", "0", "9800"]
        ], columns=["DATE", "NARRATION", "DEBIT", "CREDIT", "BALANCE"])

        result = map_columns(df)
        assert "date" in result.columns
        assert "description" in result.columns

    def test_particulars_maps_to_description(self):
        """'Particulars' (SBI-style) should map to description."""
        df = pd.DataFrame([
            ["01/01/2024", "ATM withdrawal", "2000", "0", "8000"]
        ], columns=["Txn Date", "Particulars", "Debit", "Credit", "Balance"])

        result = map_columns(df)
        assert "description" in result.columns


# ===========================================================================
# _clean_amount tests (column_mapper version)
# ===========================================================================

class TestCleanAmountMapper:

    def test_basic_amount(self):
        from column_mapper import _clean_amount
        assert _clean_amount("1000.00") == 1000.0

    def test_with_commas(self):
        from column_mapper import _clean_amount
        assert _clean_amount("10,000.00") == 10000.0

    def test_with_rupee(self):
        from column_mapper import _clean_amount
        assert _clean_amount("₹500") == 500.0

    def test_empty(self):
        from column_mapper import _clean_amount
        assert _clean_amount("") == 0.0
