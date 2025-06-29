import duckdb

class DB:
    def __init__(self, db_name):
        self.db_name = db_name
        self.con = duckdb.connect(self.db_name)

    def bootstrap(self):
        """
        Bootstrap the database by creating necessary sequences and tables.

        This method sets up:
        - `seq_account_id` for unique account IDs.
        - `seq_transaction_id` for unique transaction IDs.
        - `dim_accounts` table to store account details.
        - `fact_transactions` table to store transaction details.
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

    def get_account_ids_dict(self) -> dict:
        """
        Retrieve a dictionary mapping (financial_institution, account_number) tuples to account IDs.

        Returns:
            dict: A dictionary where keys are tuples of financial institution and account number,
                  and values are the corresponding account IDs.
        """
        rows = self.con.execute("SELECT financial_institution, account_number, account_id FROM dim_accounts").fetchall()
        return { (row[0], row[1]): row[2] for row in rows }

    def save_transaction(self, e_mail, llm_reasoning, llm_prediction, account_id):
        """
        Save a transaction to the database.

        Args:
            e_mail (dict): A dictionary containing email details such as 'from_address', 'to_address', 'uid', and 'email_date'.
            llm_reasoning (str): The reasoning provided by the language model for the transaction.
            llm_prediction (dict): A dictionary containing predicted transaction details like 'transaction_date' and 'merchant'.
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
