import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json


from unittest.mock import patch, MagicMock
from fetch_transactions import TransactionHandler

def test_get_transaction():
    # Patch Client in fetch_transactions to prevent real network calls
    with patch("fetch_transactions.Client", autospec=True) as mock_client:
        mock_llm_bridge = MagicMock()
        mock_generate = MagicMock()
        mock_generate.response = """
        Reasoning text goes here.
        {
            \"account\": \"123456789\",
            \"transaction_amount\": 100.0,
            \"transaction_date\": \"2025-06-28T12:00:00\",
            \"merchant\": \"Test Merchant\",
            \"transaction_flag\": true
        }
        """
        mock_llm_bridge.generate.return_value = mock_generate
        # Also patch list().models to avoid model check
        mock_llm_bridge.list.return_value.models = [MagicMock(model="qwen3:8b")]
        mock_client.return_value = mock_llm_bridge

        transaction_handler = TransactionHandler(model_host="http://localhost:11434", model="qwen3:8b")

        e_mail = {
            "from_address": "sender@example.com",
            "email_date": "2025-06-28T11:47:20",
            "subject": "Test Email",
            "body": "This is a test email body."
        }

        llm_reasoning, llm_prediction = transaction_handler.get_transaction(e_mail)

        assert llm_reasoning == "Reasoning text goes here.", "Expected reasoning text to match"
        expected_prediction = {
            "account": "123456789",
            "transaction_amount": 100.0,
            "transaction_date": "2025-06-28T12:00:00",
            "merchant": "Test Merchant",
            "transaction_flag": True
        }
        assert llm_prediction == expected_prediction, f"Expected prediction to match {expected_prediction}, but got {llm_prediction}"


def test_parse_model_output():
    raw_output = """
    Some reasoning text.
    {
        "account": "123456789",
        "transaction_amount": 100.0,
        "transaction_date": "2025-06-28T12:00:00",
        "merchant": "Test Merchant",
        "transaction_flag": true
    }
    """

    with patch("fetch_transactions.Client", autospec=True) as mock_client:
        mock_llm_bridge = MagicMock()
        mock_llm_bridge.list.return_value.models = [MagicMock(model="qwen3:8b")]
        mock_client.return_value = mock_llm_bridge

        transaction_handler = TransactionHandler(model_host="http://localhost:11434", model="qwen3:8b")
        llm_reasoning, llm_prediction = transaction_handler.parse_model_output(raw_output)

        assert llm_reasoning == "Some reasoning text.", "Expected reasoning text to match"
        expected_prediction = {
            "account": "123456789",
            "transaction_amount": 100.0,
            "transaction_date": "2025-06-28T12:00:00",
            "merchant": "Test Merchant",
            "transaction_flag": True
        }
        assert llm_prediction == expected_prediction, f"Expected prediction to match {expected_prediction}, but got {llm_prediction}"
