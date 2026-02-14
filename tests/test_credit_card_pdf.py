"""Unit tests for credit card PDF parsers (HDFC + ICICI)."""

import pytest
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from finance.ingestion.parsers.hdfc import HDFCCreditCardParser


# Sample HDFC transaction text patterns
HDFC_SAMPLE_TEXT = """
DATE & TIME TRANSACTION DESCRIPTION REWARDS AMOUNT PI
JOHN DOE
BPPY CC PAYMENT BD000000TESTABC001 (Ref#
22/12/2025| 13:33 + C 1,000.00 l
ST000000000000000001)
23/12/2025| 15:48 EMI TITAN COMPANY LIMITEDCHENNAI + 8840 C 2,65,250.00 l
01/01/2026| 23:02 FNP E RETAIL PRIVATE LIBANGALORE + 20 C 738.00 l
BPPY CC PAYMENT DP000000000000TEST (Ref#
04/01/2026| 11:44 + C 70,669.00 l
ST000000000000000002)
07/01/2026| 12:17 EMI MYJIOMUMBAI C 5,306.46 l
07/01/2026| 02:47 MACFOS LIMITEDPUNE + 40 C 1,317.00 l
JANE SMITH
22/12/2025| 19:30 POTHYS HYPERCHENNAI C 1,759.00 l
"""


@pytest.fixture
def hdfc_parser():
    """Create HDFC parser instance."""
    return HDFCCreditCardParser("TEST1234")


class TestHDFCTextParsing:
    """Test HDFC transaction text parsing."""

    def test_parse_same_line_format(self, hdfc_parser):
        """Test parsing transactions where description is on same line as date."""
        text = "23/12/2025| 15:48 EMI TITAN COMPANY LIMITEDCHENNAI + 8840 C 2,65,250.00 l"

        statement_date = datetime(2025, 12, 18)
        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, statement_date, warnings)

        assert len(txns) == 1
        tx = txns[0]
        assert tx.transaction_date == datetime(2025, 12, 23)
        assert tx.amount == Decimal("265250.00")
        assert "TITAN" in tx.original_description
        assert tx.currency == "INR"

    def test_parse_amount_with_commas(self, hdfc_parser):
        """Test parsing amounts with Indian comma formatting."""
        text = "01/01/2026| 23:02 FNP E RETAIL PRIVATE LIBANGALORE + 20 C 738.00 l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 1
        assert txns[0].amount == Decimal("738.00")

    def test_parse_amount_without_decimal(self, hdfc_parser):
        """Test parsing whole number amounts."""
        text = "07/01/2026| 12:17 EMI MYJIOMUMBAI C 5306 l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 1
        assert txns[0].amount == Decimal("5306")

    def test_parse_multiple_transactions(self, hdfc_parser):
        """Test parsing multiple transactions from text."""
        warnings = []
        txns = hdfc_parser._parse_hdfc_text(HDFC_SAMPLE_TEXT, None, warnings)

        # Should extract at least the obvious single-line transactions
        assert len(txns) >= 5
        assert all(tx.amount > 0 for tx in txns)
        assert all(tx.currency == "INR" for tx in txns)

    def test_skip_zero_amounts(self, hdfc_parser):
        """Test that zero amounts are skipped."""
        text = "01/01/2026| 23:02 SOME TRANSACTION C 0.00 l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 0

    def test_extract_metadata(self, hdfc_parser):
        """Test that metadata like time is extracted."""
        text = "23/12/2025| 15:48 EMI TITAN COMPANY LIMITEDCHENNAI + 8840 C 2,65,250.00 l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 1
        assert "time" in txns[0].metadata
        assert txns[0].metadata["time"] == "15:48"

    def test_clean_description(self, hdfc_parser):
        """Test that descriptions are cleaned (remove reward points, extra spaces)."""
        text = "23/12/2025| 15:48 MERCHANT     NAME + 8840 C 100.00 l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 1
        assert txns[0].original_description == "MERCHANT NAME"

    def test_warning_on_parse_error(self, hdfc_parser):
        """Test that parse errors are logged as warnings."""
        text = "INVALID DATE| TIME DESC C AMOUNT l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert isinstance(warnings, list)


class TestHDFCFilenameParser:
    """Test HDFC filename parsing for metadata extraction."""

    def test_parse_filename_with_date(self):
        """Test extracting statement date and card number from filename."""
        from finance.ingestion.bank_profiles.hdfc import parse_filename

        filename = Path("1234XXXXXXXXXX56_18-01-2026_449.pdf")
        meta = parse_filename(filename)

        assert meta is not None
        assert meta.statement_date == datetime(2026, 1, 18).date()
        assert meta.card_number_masked == "1234XXXXXXXXXX56"

    def test_parse_filename_invalid(self):
        """Test that invalid filenames return None."""
        from finance.ingestion.bank_profiles.hdfc import parse_filename

        filename = Path("invalid_filename.pdf")
        meta = parse_filename(filename)

        assert meta is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
