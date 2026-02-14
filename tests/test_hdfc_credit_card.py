"""Unit tests for HDFC Credit Card parser."""

import pytest
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from finance.ingestion.parsers.hdfc import HDFCCreditCardParser


@pytest.fixture
def hdfc_parser():
    """Create HDFC parser instance."""
    return HDFCCreditCardParser("TEST1234")


class TestHDFCFilenameDetection:
    """Test HDFC filename pattern detection."""

    def test_valid_hdfc_filename(self):
        """Test that valid HDFC filenames are detected."""
        valid_files = [
            "1234XXXXXXXXXX56_18-01-2026_449.pdf",
            "5678XXXXXXXX90_18-09-2024_123.PDF",
            "9012XXXXXXXXXX34_18-05-2020_999.pdf",
        ]

        for filename in valid_files:
            assert HDFCCreditCardParser.can_parse_filename(Path(filename))

    def test_invalid_hdfc_filename(self):
        """Test that non-HDFC filenames are rejected."""
        invalid_files = [
            "4000XXXXXXXX0001_12345_Retail_Test_NORM.pdf",  # ICICI format
            "statement_jan_2026.pdf",  # Generic name
            "random.pdf",
        ]

        for filename in invalid_files:
            assert not HDFCCreditCardParser.can_parse_filename(Path(filename))


class TestHDFCTextParsing:
    """Test HDFC transaction text parsing."""

    def test_parse_new_format(self, hdfc_parser):
        """Test parsing new format (2025+) with pipe separator."""
        text = "22/12/2025| 13:33 BPPY CC PAYMENT + 100 C 1,000.00 l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 1
        tx = txns[0]
        assert tx.transaction_date == datetime(2025, 12, 22)
        assert tx.amount == Decimal('1000.00')
        assert 'BPPY CC PAYMENT' in tx.original_description
        assert tx.metadata['format'] == 'new'

    def test_parse_old_format(self, hdfc_parser):
        """Test parsing old format (pre-2025) space-separated."""
        text = "17/08/2024 22:01:47 M S SMART BELLY FOODS CHENNAI 20 735.00"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 1
        tx = txns[0]
        assert tx.transaction_date == datetime(2024, 8, 17)
        assert tx.amount == Decimal('735.00')
        assert 'SMART BELLY FOODS' in tx.original_description
        assert tx.metadata['format'] == 'old'

    def test_parse_multiple_transactions(self, hdfc_parser):
        """Test parsing multiple transactions."""
        text = """
        22/12/2025| 13:33 BPPY CC PAYMENT C 1,000.00 l
        23/12/2025| 15:48 EMI TITAN COMPANY LIMITEDCHENNAI + 8840 C 2,65,250.00 l
        17/08/2024 22:01:47 SWIGGY NOIDA 15 498.00
        """

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 3
        assert all(tx.amount > 0 for tx in txns)
        assert all(tx.currency == 'INR' for tx in txns)

    def test_skip_zero_amounts(self, hdfc_parser):
        """Test that zero amounts are skipped."""
        text = "01/01/2026| 23:02 SOME TRANSACTION C 0.00 l"

        warnings = []
        txns = hdfc_parser._parse_hdfc_text(text, None, warnings)

        assert len(txns) == 0



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
