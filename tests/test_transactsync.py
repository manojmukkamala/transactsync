import sys
import os
from pathlib import Path

# Ensure the src directory is in the Python path
if os.path.abspath(str(Path(__file__).parent.parent / "src")) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
print(sys.path)

import unittest
from unittest.mock import patch, MagicMock
from main import transactsync

class TestMain(unittest.TestCase):

    @patch('main.EmailHandler')
    @patch('main.TransactionHandler')
    @patch('main.DB')
    @patch('main.yaml.safe_load', return_value={
        "credit_cards": {
            "account1": {
                "from_address": ["sender@example.com"],
                "subject": ["Test Subject"],
                "account_numbers": ["123456789"],
                "financial_institution": "Bank A"
            }
        }
    })
    @patch('main.prompt_builder', return_value="Mock prompt")
    def test_transactsync(self, mock_prompt_builder, mock_yaml_safe_load, MockDB, MockTransactionHandler, MockEmailHandler):
        # Mock EmailHandler
        email_handler_mock = MockEmailHandler.return_value
        email_handler_mock.get_emails.return_value = [
            {
                "uid": "1",
                "subject": "Test Subject",
                "email_date": "2025-06-28T11:47:20",
                "from_address": "<sender@example.com>",
                "to_address": "<recipient@example.com>",
                "body": "This is a test email body."
            }
        ]

        # Mock TransactionHandler
        transaction_handler_mock = MockTransactionHandler.return_value
        transaction_handler_mock.get_transaction.return_value = (
            "Mock reasoning",
            {
                "account": "123456789",
                "transaction_amount": 100.0,
                "transaction_date": "2025-06-28T12:00:00",
                "merchant": "Test Merchant",
                "transaction_flag": True,
                "account_number": "123456789"
            }
        )

        # Mock DB
        db_mock = MockDB.return_value
        db_mock.get_account_ids_dict.return_value = {('Bank A', '123456789'): 1}
        db_mock.save_transaction = MagicMock()
        db_mock.get_last_seen_uid.return_value = None
        db_mock.set_last_seen_uid = MagicMock()

        # Call the main function (no ckpt_file argument needed)
        transactsync(
            email_host="imap.example.com",
            email_port=143,
            username="user",
            password="pass",
            folder="INBOX",
            transaction_rules="tests/transaction_rules.yaml",
            db_file="test_db.duckdb",
            prompt_file="prompt.txt"
        )

        # Debug prints to verify the call arguments
        print(f"Called with args: {email_handler_mock.get_emails.call_args.args}")
        print(f"Called with kwargs: {email_handler_mock.get_emails.call_args.kwargs}")

        # Assertions
        assert 'last_seen_uid' in email_handler_mock.get_emails.call_args.kwargs, "last_seen_uid not found in call arguments"
        args, kwargs = email_handler_mock.get_emails.call_args
        transaction_handler_mock.get_transaction.assert_called_once_with(
            {
                "uid": "1",
                "subject": "Test Subject",
                "email_date": "2025-06-28T11:47:20",
                "from_address": "sender@example.com",  # Removed angle brackets
                "to_address": "recipient@example.com",   # Removed angle brackets
                "body": "This is a test email body."
            },
            "Mock prompt"
        )
        db_mock.save_transaction.assert_called_once_with(
            e_mail = {
                "uid": "1",
                "subject": "Test Subject",
                "email_date": "2025-06-28T11:47:20",
                "from_address": "sender@example.com",
                "to_address": "recipient@example.com",
                "body": "This is a test email body."
            },
            llm_reasoning = "Mock reasoning",
            llm_prediction = {
                "account": "123456789",
                "transaction_amount": 100.0,
                "transaction_date": "2025-06-28T12:00:00",
                "merchant": "Test Merchant",
                "transaction_flag": True,
                "account_number": "123456789"
            },
            account_id = 1
        )
        db_mock.set_last_seen_uid.assert_called_with("INBOX", 1)
