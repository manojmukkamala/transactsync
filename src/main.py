import os
import yaml
import argparse
from email.utils import parseaddr
from fetch_emails import EmailHandler
from fetch_transactions import TransactionHandler
from db import DB
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def prompt_builder(transaction_filters, prompt_file):
    """
    Build a prompt string for the LLM using filters from the transaction rules and a prompt template file.

    Args:
        transaction_filters (dict): Parsed YAML rules for credit cards (from transaction_rules.yaml).
        prompt_file (str): Path to the prompt template file.

    Returns:
        str: The formatted prompt string for the LLM.
    """

    from_address_filter = ""
    for account in transaction_filters["credit_cards"].keys():
        f = "`" + ", ".join(transaction_filters["credit_cards"][account]["from_address"]) + "`"
        from_address_filter = from_address_filter + f + ", "    

    subject_filter = ""
    for account in transaction_filters["credit_cards"].keys():
        f = "`" + ", ".join(transaction_filters["credit_cards"][account]["subject"]) + "`"
        subject_filter = subject_filter + f + ", "  

    account_number_filter = ""
    for account in transaction_filters["credit_cards"].keys():
        f = "`" + ", ".join(transaction_filters["credit_cards"][account]["account_numbers"]) + "`"
        account_number_filter = account_number_filter + f + ", " 

    with open(prompt_file, 'r') as f:
        llm_prompt = f.read()

    llm_prompt = llm_prompt.format(from_address_filter=from_address_filter
                            , subject_filter=subject_filter
                            , account_number_filter=account_number_filter)    
    
    return llm_prompt


def transactsync(email_host, email_port, username, password, folder, db_file, transaction_rules, prompt_file, model_host="http://localhost:11434", model="qwen3:8b"):
    """
    Main synchronization routine for fetching emails, extracting transactions, and storing them in the database.

    - Loads transaction rules and builds the LLM prompt.
    - Bootstraps the database, including inserting/updating accounts from rules.
    - Fetches new emails from the specified folder since the last checkpoint (UID).
    - For each email, uses the LLM to extract transaction details and stores valid transactions in the DB.
    - Updates the checkpoint (last seen UID) in the DB for the folder.

    Args:
        email_host (str): IMAP server address.
        email_port (int): IMAP server port.
        username (str): Email account username.
        password (str): Email account password.
        folder (str): Email folder to fetch from.
        db_file (str): Path to DuckDB database file.
        transaction_rules (str): Path to transaction rules YAML file.
        prompt_file (str): Path to prompt template file.
        model_host (str, optional): LLM model host URL. Default: "http://localhost:11434".
        model (str, optional): LLM model name. Default: "qwen3:8b".
    """

    """
    Main synchronization routine for fetching emails, extracting transactions, and storing them in the database.
    The checkpoint (last seen UID) is now stored in the database, not an external file.
    """
    with open(transaction_rules, "r") as file:
        transaction_filters = yaml.safe_load(file)

    # Prepare accounts for bootstrap
    accounts = []
    for account, details in transaction_filters["credit_cards"].items():
        for acc_num in details["account_numbers"]:
            accounts.append({
                "account_number": acc_num,
                "financial_institution": details["financial_institution"],
                "account_name": account,
                "account_owner": details.get("account_owner", ""),
                "comments": details.get("comments", "")
            })

    db_obj = DB(db_file)
    db_obj.bootstrap(accounts=accounts)
    logger.info("Bootstrap Complete.")

    llm_prompt = prompt_builder(transaction_filters, prompt_file)

    last_seen_uid = db_obj.get_last_seen_uid(folder)
    logger.info(f"last_seen_uid: {last_seen_uid}")
    max_uid = -1 if last_seen_uid is None else last_seen_uid

    email_handler = EmailHandler(logger, email_host, email_port, username, password, folder)
    e_mails = email_handler.get_emails(last_seen_uid=last_seen_uid)

    logger.info(f"Found {len(e_mails)} new emails")

    account_name_map = {}
    for account in transaction_filters["credit_cards"].keys():
        for from_address in transaction_filters["credit_cards"][account]["from_address"]:
            account_name_map[from_address] = transaction_filters["credit_cards"][account]["financial_institution"]

    acct_ids_dict = db_obj.get_account_ids_dict()
    transaction_handler = TransactionHandler(logger=logger, model_host=model_host, model=model)

    for e_mail in e_mails:
        llm_reasoning, llm_prediction = transaction_handler.get_transaction(e_mail, llm_prompt)
        _, e_mail['from_address'] = parseaddr(e_mail['from_address'])
        _, e_mail['to_address'] = parseaddr(e_mail['to_address'])
        if llm_prediction and llm_prediction["transaction_flag"] == True:
            financial_institution = account_name_map[e_mail['from_address']]
            account_id = acct_ids_dict[(financial_institution, llm_prediction['account_number'])]
            llm_reasoning = llm_reasoning.replace('"', '`').replace("'", "`")
            logger.info(f"from_address: {e_mail["from_address"]}")
            logger.info(f"to_address: {e_mail["to_address"]}")
            logger.info(f"email_uid: {e_mail['uid']}")
            logger.info(f"email_date: {e_mail["email_date"]}")
            logger.info(f"email_subject: {e_mail["subject"]}")
            logger.info(f"llm_prediction: {llm_prediction}")
            # logger.info(f"llm_reasoning: {llm_reasoning}")
            db_obj.save_transaction(e_mail=e_mail, llm_reasoning=llm_reasoning, llm_prediction=llm_prediction, account_id=account_id)
            logger.info("Transaction stored to DB")
        elif llm_prediction["transaction_flag"] == False:
            logger.info("Skipping non-transaction")
            # logger.info(f"from_address: {e_mail["from_address"]}")
            # logger.info(f"email_subject: {e_mail["subject"]}")
        # print("-" * 100)
        max_uid = max(max_uid, int(e_mail["uid"]))
        db_obj.set_last_seen_uid(folder, max_uid)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=(argparse.RawDescriptionHelpFormatter)
    )
    parser.add_argument(
        "--email_host", 
        help="Email Host (IMAP Server Address)", 
        default=os.environ.get("EMAIL_HOST"),
        required=False
    )
    parser.add_argument(
        "--email_port", 
        help="Email Host (IMAP Server Address)", 
        default=os.environ.get("EMAIL_PORT"),
        required=False
    )
    parser.add_argument(
        "--username", 
        help="Email Account Username", 
        default=os.environ.get("EMAIL_USERNAME"),
        required=False
    )
    parser.add_argument(
        "--password", 
        help="Email Account Password", 
        default=os.environ.get("EMAIL_PASSWORD"),
        required=False
    )
    parser.add_argument(
        "--folder", 
        help="Folder Name", 
        default=os.environ.get("EMAIL_FOLDER", "INBOX"),
        required=False
    )
    parser.add_argument(
        "--db_file", 
        help="Duckdb database File", 
        default="/workspace/db/finances.db"
    )    
    parser.add_argument(
        "--transaction_rules", 
        help="Transaction Rules File", 
        default="/workspace/transaction_rules.yaml"
    )
    parser.add_argument(
        "--prompt_file", 
        help="Prompt File", 
        default="/workspace/prompt.txt"
    )
    parser.add_argument(
        "--model_host", 
        help="Model Host (default: http://localhost:11434)", 
        default=os.environ.get("MODEL_HOST", "http://localhost:11434"),
        required=False        
    )
    parser.add_argument(
        "--model", 
        help="Model Name (default: qwen3:8b)", 
        default=os.environ.get("MODEL_NAME", "qwen3:8b"),
        required=False         
    )
    args = parser.parse_args()

    # Validate required arguments (env or CLI)
    missing = []
    if not args.email_host:
        missing.append("email_host (or EMAIL_HOST env var)")
    if not args.email_port:
        missing.append("email_port (or EMAIL_PORT env var)")
    if not args.username:
        missing.append("username (or EMAIL_USERNAME env var)")
    if not args.password:
        missing.append("password (or EMAIL_PASSWORD env var)")
    if not args.folder:
        missing.append("folder (or EMAIL_FOLDER env var)")
    if missing:
        parser.error("Missing required arguments: " + ", ".join(missing))

    transactsync(
        args.email_host, args.email_port, args.username, args.password, args.folder, args.db_file,
        args.transaction_rules, args.prompt_file,
        model_host=args.model_host, model=args.model
    )