"""
Tests for garbage_filter.py
Covers: header detection, blacklist filtering, date validation, empty row removal
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from garbage_filter import filter_garbage, _is_header_row, _is_blacklisted, _has_valid_date, _is_empty_row


# ===========================================================================
# _is_header_row tests
# ===========================================================================

class TestIsHeaderRow:

    def test_detects_header_row(self):
        row = {"date": "Date", "description": "Narration", "debit": "Withdrawal", "credit": "Deposit", "balance": "Balance"}
        assert _is_header_row(row) == True

    def test_real_transaction_not_header(self):
        row = {"date": "01/01/2024", "description": "Zomato UPI payment", "debit": "500", "credit": "", "balance": "9500"}
        assert _is_header_row(row) == False

    def test_partial_header_keywords_not_flagged(self):
        """Only 1 header keyword — should not be flagged (threshold is 2)."""
        row = {"date": "01/01/2024", "description": "balance inquiry", "debit": "0", "credit": "0", "balance": "5000"}
        assert _is_header_row(row) == False


# ===========================================================================
# _is_blacklisted tests
# ===========================================================================

class TestIsBlacklisted:

    def test_opening_balance_blacklisted(self):
        row = {"date": "01/01/2024", "description": "Opening Balance", "debit": "0", "credit": "0", "balance": "10000"}
        assert _is_blacklisted(row) == True

    def test_closing_balance_blacklisted(self):
        row = {"date": "31/01/2024", "description": "Closing Balance", "debit": "0", "credit": "0", "balance": "15000"}
        assert _is_blacklisted(row) == True

    def test_total_row_blacklisted(self):
        row = {"date": "", "description": "Total", "debit": "5000", "credit": "8000", "balance": ""}
        assert _is_blacklisted(row) == True

    def test_normal_transaction_not_blacklisted(self):
        row = {"date": "05/01/2024", "description": "Swiggy order payment", "debit": "350", "credit": "", "balance": "9650"}
        assert _is_blacklisted(row) == False

    def test_page_footer_blacklisted(self):
        row = {"date": "", "description": "Page 1 of 3 - generated on 01/01/2024", "debit": "", "credit": "", "balance": ""}
        assert _is_blacklisted(row) == True


# ===========================================================================
# _has_valid_date tests
# ===========================================================================

class TestHasValidDate:

    def test_dd_mm_yyyy_format(self):
        row = {"date": "01/01/2024", "description": "Test"}
        assert _has_valid_date(row) == True

    def test_dd_mm_yy_format(self):
        row = {"date": "01-01-24", "description": "Test"}
        assert _has_valid_date(row) == True

    def test_no_date_returns_false(self):
        row = {"date": "", "description": "Some text without date"}
        assert _has_valid_date(row) == False

    def test_date_in_first_list_value(self):
        """List-style rows should check first element."""
        row = ["01/01/2024", "Salary credit", "0", "5000", "15000"]
        assert _has_valid_date(row) == True

    def test_missing_date_key_returns_false(self):
        row = {"description": "No date here", "debit": "500"}
        assert _has_valid_date(row) == False


# ===========================================================================
# _is_empty_row tests
# ===========================================================================

class TestIsEmptyRow:

    def test_empty_dict_is_empty(self):
        row = {"date": "", "description": "", "debit": "", "credit": "", "balance": ""}
        assert _is_empty_row(row) == True

    def test_row_with_data_not_empty(self):
        row = {"date": "01/01/2024", "description": "UPI payment", "debit": "500", "credit": "", "balance": "9500"}
        assert _is_empty_row(row) == False

    def test_nan_values_treated_as_empty(self):
        row = {"date": "nan", "description": "nan", "debit": "nan"}
        assert _is_empty_row(row) == True


# ===========================================================================
# filter_garbage integration tests
# ===========================================================================

class TestFilterGarbage:

    def test_removes_header_row(self):
        rows = [
            {"date": "Date", "description": "Narration", "debit": "Withdrawal", "credit": "Deposit", "balance": "Balance"},
            {"date": "01/01/2024", "description": "Zomato", "debit": "500", "credit": "", "balance": "9500"},
        ]
        result = filter_garbage(rows)
        assert len(result) == 1
        assert result[0]["description"] == "Zomato"

    def test_removes_opening_balance(self):
        rows = [
            {"date": "01/01/2024", "description": "Opening Balance", "debit": "0", "credit": "0", "balance": "10000"},
            {"date": "02/01/2024", "description": "Swiggy", "debit": "300", "credit": "", "balance": "9700"},
        ]
        result = filter_garbage(rows)
        assert len(result) == 1
        assert result[0]["description"] == "Swiggy"

    def test_removes_rows_without_dates(self):
        rows = [
            {"date": "", "description": "Some footer text", "debit": "", "credit": "", "balance": ""},
            {"date": "03/01/2024", "description": "Netflix", "debit": "649", "credit": "", "balance": "9051"},
        ]
        result = filter_garbage(rows)
        assert len(result) == 1
        assert result[0]["description"] == "Netflix"

    def test_keeps_valid_transactions(self):
        rows = [
            {"date": "01/01/2024", "description": "Salary NEFT", "debit": "0", "credit": "50000", "balance": "60000"},
            {"date": "02/01/2024", "description": "Rent UPI", "debit": "15000", "credit": "0", "balance": "45000"},
            {"date": "03/01/2024", "description": "Groceries", "debit": "2000", "credit": "0", "balance": "43000"},
        ]
        result = filter_garbage(rows)
        assert len(result) == 3

    def test_empty_input_returns_empty(self):
        assert filter_garbage([]) == []

    def test_all_garbage_returns_empty(self):
        rows = [
            {"date": "Date", "description": "Narration", "debit": "Debit", "credit": "Credit", "balance": "Balance"},
            {"date": "01/01/2024", "description": "Opening Balance", "debit": "0", "credit": "0", "balance": "10000"},
            {"date": "31/01/2024", "description": "Closing Balance", "debit": "0", "credit": "0", "balance": "12000"},
        ]
        result = filter_garbage(rows)
        assert len(result) == 0
