"""Unit tests for HDFC bank PDF parser metadata helpers."""

from finance.ingestion.bank_account_pdf import BankPdfParser


def test_extract_account_metadata():
    text = """
    HDFC BANK LIMITED
    Cust ID : 12345678
    Account Number : 50100000012345
    """
    meta = BankPdfParser._extract_account_metadata(text)

    assert meta["customer_id"] == "12345678"
    assert meta["account_number_masked"] == "5010XXXXXX2345"
