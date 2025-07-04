import duckdb

class DB:
    """
    Database handler for DuckDB, supporting account bootstrapping, transaction logging, and email checkpointing.
    """

    def __init__(self, db_name):
        self.db_name = db_name
        self.con = duckdb.connect(self.db_name)

    def bootstrap(self, accounts=None):
        """
        Bootstrap the database by creating necessary sequences and tables, and optionally insert/update accounts.

        This method sets up:
        - `seq_account_id` for unique account IDs.
        - `seq_transaction_id` for unique transaction IDs.
        - `dim_accounts` table to store account details.
        - `fact_transactions` table to store transaction details.
        - `email_checkpoints` table to store the last seen email UID for checkpointing (replaces external file).

        If `accounts` is provided, each account dict is inserted into `dim_accounts` if it does not already exist (by financial_institution and account_number).

        Args:
            accounts (list[dict], optional): List of account dicts to insert. Each dict should have at least
                'account_number' and 'financial_institution'.
        """
        
        self.con.execute("CREATE SEQUENCE IF NOT EXISTS seq_account_id START WITH 1 INCREMENT BY 1;")
        self.con.execute("CREATE SEQUENCE IF NOT EXISTS seq_transaction_id START WITH 1 INCREMENT BY 1;")
        
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS dim_accounts (
                load_time TIMESTAMP DEFAULT(CURRENT_TIMESTAMP),
                load_by VARCHAR,
                account_id INTEGER PRIMARY KEY DEFAULT nextval('seq_account_id'),
                account_number VARCHAR,
                financial_institution VARCHAR,
                account_name VARCHAR,
                account_owner VARCHAR,
                active BOOLEAN,
                comments VARCHAR
            );
        """)

        # Insert accounts if provided
        if accounts:
            for acc in accounts:
                # Only insert if not already present
                exists = self.con.execute(
                    "SELECT 1 FROM dim_accounts WHERE financial_institution=? AND account_number=?",
                    (acc['financial_institution'], acc['account_number'])
                ).fetchone()
                if not exists:
                    self.con.execute(
                        """
                        INSERT INTO dim_accounts (
                            load_by, account_number, financial_institution, account_name, account_owner, active, comments
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            'agent',
                            acc['account_number'],
                            acc['financial_institution'],
                            acc.get('account_name', ''),
                            acc.get('account_owner', ''),
                            True,
                            acc.get('comments', '')
                        )
                    )

        self.con.execute("""
            CREATE TABLE IF NOT EXISTS fact_transactions (
                load_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                load_by STRING,
                transaction_id INTEGER PRIMARY KEY DEFAULT nextval('seq_transaction_id'),
                transaction_date TIMESTAMP,
                transaction_amount FLOAT,
                merchant STRING,
                category STRING,
                account_id INTEGER REFERENCES dim_accounts(account_id),
                expense_owner STRING,
                from_address STRING,
                to_address STRING,
                email_uid STRING,
                email_date TIMESTAMP,
                llm_reasoning STRING
            );
        """)

        self.con.execute("CREATE SEQUENCE IF NOT EXISTS seq_email_checkpoint_id START WITH 1 INCREMENT BY 1;")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS email_checkpoints (
                id BIGINT PRIMARY KEY DEFAULT nextval('seq_email_checkpoint_id'),
                folder VARCHAR NOT NULL,
                last_seen_uid INTEGER,
                UNIQUE(folder)
            );
        """)

    def get_last_seen_uid(self, folder):
        """
        Retrieve the last seen email UID for a specific folder from the email_checkpoints table.

        Args:
            folder (str): The email folder name.

        Returns:
            int or None: The last seen UID, or None if not set.
        """
        row = self.con.execute("SELECT last_seen_uid FROM email_checkpoints WHERE folder=?", (folder,)).fetchone()
        return row[0] if row else None

    def set_last_seen_uid(self, folder, uid):
        """
        Update or insert the last seen email UID for a specific folder in the email_checkpoints table.

        Args:
            folder (str): The email folder name.
            uid (int): The UID to store as the checkpoint.
        """
        if self.con.execute("SELECT 1 FROM email_checkpoints WHERE folder=?", (folder,)).fetchone():
            self.con.execute("UPDATE email_checkpoints SET last_seen_uid=? WHERE folder=?", (uid, folder))
        else:
            self.con.execute("INSERT INTO email_checkpoints (folder, last_seen_uid) VALUES (?, ?)", (folder, uid))

    def get_account_ids_dict(self) -> dict:
        """
        Retrieve a dictionary mapping (financial_institution, account_number) tuples to account IDs from dim_accounts.

        Returns:
            dict: A dictionary where keys are tuples of (financial_institution, account_number),
                  and values are the corresponding account IDs.
        """
        rows = self.con.execute("SELECT financial_institution, account_number, account_id FROM dim_accounts").fetchall()
        return { (row[0], row[1]): row[2] for row in rows }

    def save_transaction(self, e_mail, llm_reasoning, llm_prediction, account_id):
        """
        Save a transaction to the database (fact_transactions).

        Args:
            e_mail (dict): Dictionary with email details ('from_address', 'to_address', 'uid', 'email_date').
            llm_reasoning (str): Reasoning provided by the language model for the transaction.
            llm_prediction (dict): Dict with predicted transaction details ('transaction_date', 'merchant', etc).
            account_id (int): The ID of the account associated with the transaction.
        """
        q = f"""INSERT INTO fact_transactions (
                load_by,
                transaction_date,
                transaction_amount,
                merchant,
                account_id,
                from_address,
                to_address,
                email_uid,
                email_date,
                llm_reasoning)
                VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
                )
            """
        self.con.execute(q, (
            'agent',
            llm_prediction['transaction_date'],
            llm_prediction['transaction_amount'],
            llm_prediction['merchant'],
            account_id,
            e_mail['from_address'],
            e_mail['to_address'],
            int(e_mail['uid']),
            e_mail['email_date'],
            llm_reasoning
        ))
