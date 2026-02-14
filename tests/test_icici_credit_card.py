"""Unit tests for ICICI Credit Card parser."""

import pytest
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from finance.ingestion.parsers.icici import ICICICreditCardParser


@pytest.fixture
def icici_parser():
    """Create ICICI parser instance."""
    return ICICICreditCardParser("test1234")


class TestICICIFilenameDetection:
    """Test ICICI filename pattern detection."""

    def test_valid_icici_filename(self):
        """Test that valid ICICI filenames are detected."""
        valid_files = [
            "4000XXXXXXXX0001_12345_Retail_Test_NORM.pdf",
            "4111XXXXXXXX0002_67890_Retail_Premium_NORM.pdf",
            "4000XXXXXXXX0001_99999_Retail_Test_NORM.PDF",
        ]

        for filename in valid_files:
            assert ICICICreditCardParser.can_parse_filename(Path(filename))

    def test_invalid_icici_filename(self):
        """Test that non-ICICI filenames are rejected."""
        invalid_files = [
            "1234XXXXXXXXXX56_18-01-2026_449.pdf",  # HDFC format
            "statement_jan_2026.pdf",  # Generic name
            "random.pdf",
        ]

        for filename in invalid_files:
            assert not ICICICreditCardParser.can_parse_filename(Path(filename))


class TestICICITextParsing:
    """Test ICICI transaction text parsing."""

    def test_parse_debit_transaction(self, icici_parser):
        """Test parsing a debit transaction."""
        text = "19/11/2025 12366165854 SANGEETHA VEG CHEENAI IN 609.00"

        warnings = []
        txns = icici_parser._parse_icici_text(text, warnings)

        assert len(txns) == 1
        tx = txns[0]
        assert tx.transaction_date == datetime(2025, 11, 19)
        assert tx.amount == Decimal('609.00')
        assert 'SANGEETHA VEG' in tx.original_description
        assert tx.external_id == "12366165854"
        assert tx.transaction_type.value == 'expense'
        assert tx.metadata['country_code'] == 'IN'

    def test_parse_credit_transaction(self, icici_parser):
        """Test parsing a credit transaction (with CR suffix)."""
        text = "04/12/2025 12450630825 BBPS Payment received IN 2,722.86 CR"

        warnings = []
        txns = icici_parser._parse_icici_text(text, warnings)

        assert len(txns) == 1
        tx = txns[0]
        assert tx.transaction_date == datetime(2025, 12, 4)
        assert tx.amount == Decimal('2722.86')
        assert tx.transaction_type.value == 'income'
        assert tx.metadata['is_credit'] is True

    def test_parse_amount_with_comma(self, icici_parser):
        """Test parsing amounts with Indian comma formatting."""
        text = "18/11/2025 12366350031 GEETHAM CHEENAI IN 1,848.00"

        warnings = []
        txns = icici_parser._parse_icici_text(text, warnings)

        assert len(txns) == 1
        assert txns[0].amount == Decimal('1848.00')

    def test_parse_multiple_transactions(self, icici_parser):
        """Test parsing multiple transactions."""
        text = """
        19/11/2025 12366165854 SANGEETHA VEG CHEENAI IN 609.00
        18/11/2025 12366350031 GEETHAM CHEENAI IN 1,848.00
        24/11/2025 12394901570 SANGEEETHA VEG CHENNAI IN 718.00
        """

        warnings = []
        txns = icici_parser._parse_icici_text(text, warnings)

        assert len(txns) == 3
        assert all(tx.amount > 0 for tx in txns)
        assert all(tx.currency == 'INR' for tx in txns)

    def test_skip_zero_amounts(self, icici_parser):
        """Test that zero amounts are skipped."""
        text = "19/11/2025 12366165854 ZERO TRANSACTION IN 0.00"

        warnings = []
        txns = icici_parser._parse_icici_text(text, warnings)

        assert len(txns) == 0

    def test_extract_card_number_from_text(self, icici_parser):
        text = "Credit Card No: 4111 XXXX XXXX 0002"
        assert icici_parser._extract_card_number_from_text(text) == "4111XXXXXXXX0002"

    def test_extract_total_amount_due(self, icici_parser):
        text = "STATEMENT SUMMARY\nTotal Amount due\n`8,000.00 = + + -\nMinimum Amount due\n`400.00"
        assert icici_parser._extract_total_amount_due(text) == Decimal("8000.00")

    def test_reconcile_net_amount_with_credit(self, icici_parser):
        text = "\n".join(
            [
                "STATEMENT SUMMARY",
                "Total Amount due",
                "`800.00 = + + -",
                "19/11/2025 12366165854 MERCHANT ONE IN 1,000.00",
                "20/11/2025 12366165855 PAYMENT RECEIVED IN 200.00 CR",
            ]
        )
        warnings = []
        txns = icici_parser._parse_icici_text(text, warnings)
        recon = icici_parser._reconcile(text, txns)
        assert recon.expected_total == Decimal("800.00")
        assert recon.actual_total == Decimal("800.00")
        assert recon.matches is True


@pytest.mark.skipif(
    not Path("icici/4000XXXXXXXX0001_12345_Retail_Test_NORM.pdf").exists(),
    reason="Sample PDF not available"
)
class TestICICIRealPDF:
    """Integration tests with real ICICI PDF."""

    def test_parse_real_pdf(self, icici_parser):
        """Test parsing a real ICICI PDF."""
        pdf_file = Path("icici/4000XXXXXXXX0001_12345_Retail_Test_NORM.pdf")

        assert icici_parser.can_parse(pdf_file)

        result = icici_parser.parse(pdf_file)

        assert result.success
        assert len(result.transactions) > 0
        assert result.metadata['bank'] == 'icici'
        assert 'card_number' in result.metadata

        # Check first transaction has required fields
        tx = result.transactions[0]
        assert tx.transaction_date is not None
        assert tx.amount > 0
        assert tx.original_description
        assert tx.currency == 'INR'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
