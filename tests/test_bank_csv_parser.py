"""Tests for bank CSV parser metadata extraction."""

from pathlib import Path

from finance.ingestion.parsers.bank_csv import HDFCBankCsvParser


def test_extract_account_number_from_filename_masked_token():
    file_path = Path("Acct_Statement_XXXXXXXX0001_05022026 (2).txt")
    account = HDFCBankCsvParser._extract_account_number_from_filename(file_path)
    assert account == "XXXXXXXX0001"

