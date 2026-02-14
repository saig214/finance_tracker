"""Tests for deterministic parser detection text rules."""

from finance.ingestion.bank_account_pdf import BankPdfParser
from finance.ingestion.parsers.hdfc import HDFCCreditCardParser
from finance.ingestion.parsers.icici import ICICICreditCardParser


def test_hdfc_credit_card_text_rule_positive():
    text = """
    Diners Black Credit Card Statement
    HDFC Bank Credit Cards GSTIN: 33AAACH2702H2Z6
    Credit Card No. 12340000XXXX5678
    Statement Date 18 Dec, 2025
    Billing Period : 19 Nov, 2025 - 18 Dec, 2025
    """
    assert HDFCCreditCardParser._is_hdfc_credit_card_text(text)


def test_hdfc_credit_card_text_rule_rejects_bank_statement():
    text = """
    HDFC BANK LIMITED
    Account Branch : Anna Nagar
    Cust ID : 12345678
    Date Narration Withdrawal Amount Deposit Amount Closing Balance
    """
    assert not HDFCCreditCardParser._is_hdfc_credit_card_text(text)


def test_hdfc_credit_card_legacy_text_rule_positive():
    text = """
    Diners Club International Credit Card Statement
    HDFC Bank Credit Cards GSTIN : 33AAACH2702H2Z6
    Statement for HDFC Bank Credit Card
    Date:18/06/2024
    Statement Card No: 5678 00XXXX 1234 0
    Payment Due Date Total Dues Minimum Amount Due
    """
    assert HDFCCreditCardParser._is_hdfc_credit_card_legacy_text(text)


def test_icici_credit_card_text_rule_positive():
    text = """
    ICICI Bank
    STATEMENT DATE May 18, 2024
    PAYMENT DUE DATE June 5, 2024
    Total Amount due
    Minimum Amount due
    """
    assert ICICICreditCardParser._is_icici_credit_card_text(text)


def test_icici_credit_card_text_rule_rejects_hdfc():
    text = """
    HDFC Bank Credit Cards
    Billing Period : 19 Nov, 2025 - 18 Dec, 2025
    Statement Date 18 Dec, 2025
    """
    assert not ICICICreditCardParser._is_icici_credit_card_text(text)


def test_hdfc_bank_statement_text_rule_positive():
    text = """
    HDFC BANK LIMITED
    Account Branch : Anna Nagar 5th Avenue
    Cust ID : 12345678
    Account Number : 5010XXXXXXXX0001
    IFSC : HDFC0000001 MICR : 600000001
    Date Narration Withdrawal Amount Deposit Amount Closing Balance
    """
    assert BankPdfParser._is_hdfc_bank_statement_text(text)


def test_hdfc_bank_statement_text_rule_rejects_credit_card():
    text = """
    HDFC Bank Credit Cards
    Credit Card Statement
    Billing Period : 19 Nov, 2025 - 18 Dec, 2025
    Payment Due Date
    """
    assert not BankPdfParser._is_hdfc_bank_statement_text(text)
