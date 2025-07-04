def test_set_and_get_last_seen_uid_for_multiple_folders():
    db = DB(':memory:')
    db.bootstrap()
    # Initially, no checkpoint for either folder
    assert db.get_last_seen_uid('INBOX') is None
    assert db.get_last_seen_uid('Archive') is None
    # Set for INBOX
    db.set_last_seen_uid('INBOX', 42)
    assert db.get_last_seen_uid('INBOX') == 42
    assert db.get_last_seen_uid('Archive') is None
    # Set for Archive
    db.set_last_seen_uid('Archive', 99)
    assert db.get_last_seen_uid('INBOX') == 42
    assert db.get_last_seen_uid('Archive') == 99

def test_update_last_seen_uid_for_folder():
    db = DB(':memory:')
    db.bootstrap()
    db.set_last_seen_uid('INBOX', 10)
    assert db.get_last_seen_uid('INBOX') == 10
    db.set_last_seen_uid('INBOX', 55)
    assert db.get_last_seen_uid('INBOX') == 55

def test_get_last_seen_uid_returns_none_for_unknown_folder():
    db = DB(':memory:')
    db.bootstrap()
    assert db.get_last_seen_uid('NonExistentFolder') is None
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db import DB

def test_bootstrap():
    db = DB(':memory:')
    db.bootstrap()

    # Check if tables and sequences are created
    result = db.con.execute("SELECT COUNT(*) FROM dim_accounts").fetchone()
    assert result[0] == 0, "Table dim_accounts should be empty after bootstrap"

    result = db.con.execute("SELECT COUNT(*) FROM fact_transactions").fetchone()
    assert result[0] == 0, "Table fact_transactions should be empty after bootstrap"

def test_get_account_ids_dict():
    db = DB(':memory:')
    db.bootstrap()

    # Insert some accounts
    db.con.execute("""
        INSERT INTO dim_accounts (account_number, financial_institution, account_name, account_owner, active, comments)
        VALUES ('123456789', 'Bank A', 'Account 1', 'Owner 1', true, 'Comment 1'),
               ('987654321', 'Bank B', 'Account 2', 'Owner 2', false, 'Comment 2')
    """)

    account_ids_dict = db.get_account_ids_dict()
    expected_dict = {
        ('Bank A', '123456789'): 1,
        ('Bank B', '987654321'): 2
    }
    assert account_ids_dict == expected_dict, f"Expected {expected_dict}, but got {account_ids_dict}"

def test_save_transaction():
    db = DB(':memory:')
    db.bootstrap()

    # Insert an account to reference
    db.con.execute("""
        INSERT INTO dim_accounts (account_number, financial_institution, account_name, account_owner, active, comments)
        VALUES ('123456789', 'Bank A', 'Account 1', 'Owner 1', true, 'Comment 1')
    """)

    e_mail = {
        'from_address': 'example@example.com',
        'to_address': 'recipient@example.com',
        'uid': '123',
        'email_date': '2025-06-28T12:00:00'
    }

    llm_reasoning = "This is a test transaction"
    llm_prediction = {
        'transaction_date': '2025-06-28T12:00:00',
        'transaction_amount': 100.0,
        'merchant': 'Test Merchant',
        'account_number': '123456789'
    }

    account_id = db.get_account_ids_dict()[('Bank A', '123456789')]
    db.save_transaction(e_mail, llm_reasoning, llm_prediction, account_id)

    # Check if the transaction is saved
    result = db.con.execute("SELECT COUNT(*) FROM fact_transactions").fetchone()
    assert result[0] == 1, "Transaction should be inserted into fact_transactions"

def test_bootstrap_with_accounts_inserts_accounts():
    db = DB(':memory:')
    accounts = [
        {
            'account_number': '111',
            'financial_institution': 'Bank X',
            'account_name': 'Test Account X',
            'account_owner': 'Owner X',
            'comments': 'First insert'
        },
        {
            'account_number': '222',
            'financial_institution': 'Bank Y',
            'account_name': 'Test Account Y',
            'account_owner': 'Owner Y',
            'comments': 'Second insert'
        }
    ]
    db.bootstrap(accounts=accounts)
    rows = db.con.execute("SELECT account_number, financial_institution, account_name, account_owner, comments FROM dim_accounts").fetchall()
    assert len(rows) == 2
    assert ('111', 'Bank X', 'Test Account X', 'Owner X', 'First insert') in rows
    assert ('222', 'Bank Y', 'Test Account Y', 'Owner Y', 'Second insert') in rows

def test_bootstrap_with_accounts_deduplicates_on_rerun():
    db = DB(':memory:')
    accounts1 = [
        {
            'account_number': '111',
            'financial_institution': 'Bank X',
            'account_name': 'Test Account X',
            'account_owner': 'Owner X',
            'comments': 'First insert'
        }
    ]
    accounts2 = [
        {
            'account_number': '111',
            'financial_institution': 'Bank X',
            'account_name': 'Test Account X',
            'account_owner': 'Owner X',
            'comments': 'First insert'
        },
        {
            'account_number': '333',
            'financial_institution': 'Bank Z',
            'account_name': 'Test Account Z',
            'account_owner': 'Owner Z',
            'comments': 'Third insert'
        }
    ]
    db.bootstrap(accounts=accounts1)
    db.bootstrap(accounts=accounts2)
    rows = db.con.execute("SELECT account_number, financial_institution FROM dim_accounts").fetchall()
    assert ('111', 'Bank X') in rows
    assert ('333', 'Bank Z') in rows
    assert len(rows) == 2
