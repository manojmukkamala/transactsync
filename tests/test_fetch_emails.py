import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import imaplib
from unittest.mock import patch, MagicMock, call
from fetch_emails import EmailHandler

def test_imap_bridge():
    # Mock imaplib.IMAP4 to avoid actual network calls
    with patch('imaplib.IMAP4', return_value=MagicMock()) as mock_imap:
        email_handler = EmailHandler(host='imap.example.com', port=143, username='user', password='pass', folder='INBOX')
        connection = email_handler.imap_bridge()
        
        assert isinstance(connection, MagicMock), "Connection should be an instance of MagicMock"
        mock_imap.assert_called_with('imap.example.com', 143)
        connection.login.assert_called_once_with('user', 'pass')

def test_get_email_uids():
    # Mock imaplib.IMAP4 and its methods
    mock_connection = MagicMock()
    mock_connection.select.return_value = ('OK', [])
    mock_connection.uid.return_value = ('OK', [b'1 2 3'])
    
    with patch('imaplib.IMAP4', return_value=mock_connection):
        email_handler = EmailHandler(host='imap.example.com', port=143, username='user', password='pass', folder='INBOX')
        email_handler.imap_bridge()  # Ensure the connection is established
        uids = email_handler.get_email_uids(last_seen_uid=None)
        
        assert uids == [b'1', b'2', b'3'], "Expected UIDs to be [b'1', b'2', b'3']"
        mock_connection.select.assert_called_once_with('"INBOX"')
        mock_connection.uid.assert_called_once_with("search", None, "ALL")

def test_get_emails():
    # Mock imaplib.IMAP4 and its methods
    mock_connection = MagicMock()
    mock_connection.select.return_value = ('OK', [])
    
    raw_email1 = "\r\n".join([
        "Return-Path: <sender@example.com>",
        "Received: from mail.example.com...",
        "Date: Wed, 28 Jun 2025 11:47:20 -0400 (EDT)",
        "From: Sender Name <sender@example.com>",
        "To: Recipient Name <recipient@example.com>",
        "Subject: Test Email 1",
        "Message-ID: <CA+dX9n=example1@example.com>",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=\"UTF-8\"",
        "",
        "This is the first test email body."
    ]).encode("utf-8")

    raw_email2 = "\r\n".join([
        "Return-Path: <sender@example.com>",
        "Received: from mail.example.com (mail.example.com. [93.184.216.34])",
        "    by mx.google.com with ESMTPS id n17sor305048wrb.2025.06.28.11.48.20",
        "    for <recipient@example.com>;",
        "Date: Wed, 28 Jun 2025 11:48:20 -0400 (EDT)",
        "From: Sender Name <sender@example.com>",
        "To: Recipient Name <recipient@example.com>",
        "Subject: Test Email 2",
        "Message-ID: <CA+dX9n=example2@example.com>",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=\"UTF-8\"",
        "",
        "This is the second test email body."
    ]).encode("utf-8")
    
    mock_connection.uid.side_effect = [
        ('OK', [b'1 2']),
        ('OK', [(b'', raw_email1)]),
        ('OK', [(b'', raw_email2)])
    ]
    
    with patch('imaplib.IMAP4', return_value=mock_connection):
        email_handler = EmailHandler(host='imap.example.com', port=143, username='user', password='pass', folder='INBOX')
        email_handler.imap_bridge()  # Ensure the connection is established
        emails = email_handler.get_emails(last_seen_uid=None)
        
        assert len(emails) == 2, "Expected to retrieve 2 emails"
        for i, email in enumerate(emails):
            assert email['uid'].decode('utf-8') == str(i + 1), f"UID mismatch for email {i+1}"
            assert email['subject'] == f'Test Email {i+1}', f'Subject mismatch for email {i+1}'
            assert 'email_date' in email, "Email date missing"
            assert 'from_address' in email, "From address missing"
            assert 'to_address' in email, "To address missing"
            assert 'body' in email, "Body missing"
            
        mock_connection.select.assert_called_once_with('"INBOX"')
        mock_connection.uid.assert_has_calls([
            call("search", None, "ALL"),
            call("fetch", b'1', "(RFC822)"),
            call("fetch", b'2', "(RFC822)")
        ])
