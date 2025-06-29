import yaml
import argparse
from email.utils import parseaddr
from fetch_emails import EmailHandler
from fetch_transactions import TransactionHandler
from db import DB

def prompt_builder(transaction_filters, prompt_file):

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


def transactsync(email_host, email_port, username, password, folder, ckpt_file, transaction_rules, db_file, prompt_file):

    try:
        if ckpt_file:
            with open(ckpt_file) as f:
                last_seen_uid = int(f.read().strip() or 0)
        else:
            last_seen_uid = None
    except FileNotFoundError:
        last_seen_uid = None

    print(f"last_seen_uid: {last_seen_uid}")
    max_uid = -1 if last_seen_uid is None else last_seen_uid

    email_handler = EmailHandler(email_host, email_port, username, password, folder)
    e_mails = email_handler.get_emails(last_seen_uid=last_seen_uid)  # Pass last_seen_uid as a keyword argument

    print(f"Found {len(e_mails)} new emails")
    print("-" * 100)

    with open(transaction_rules, "r") as file:
        transaction_filters = yaml.safe_load(file)      

    llm_prompt = prompt_builder(transaction_filters, prompt_file)
    
    account_name_map = {}
    for account in transaction_filters["credit_cards"].keys():
        for from_address in transaction_filters["credit_cards"][account]["from_address"]:
            account_name_map[from_address] = transaction_filters["credit_cards"][account]["financial_institution"]    

    db_obj = DB(db_file)
    db_obj.bootstrap()
    
    acct_ids_dict = db_obj.get_account_ids_dict()
        
    transaction_handler = TransactionHandler(model_host="http://localhost:11434", model="qwen3:8b", request_timeout=300.0)

    for e_mail in e_mails: 
        
        llm_reasoning, llm_prediction = transaction_handler.get_transaction(e_mail, llm_prompt)

        _, e_mail['from_address'] = parseaddr(e_mail['from_address'])
        _, e_mail['to_address'] = parseaddr(e_mail['to_address'])     

        if llm_prediction and llm_prediction["transaction_flag"] == True:

            financial_institution = account_name_map[e_mail['from_address']]
            account_id = acct_ids_dict[(financial_institution, llm_prediction['account_number'])]

            llm_reasoning = llm_reasoning.replace('"', '`').replace("'", "`")               

            print(f"from_address: {e_mail["from_address"]}")
            print(f"to_address: {e_mail["to_address"]}")
            print(f"email_uid: {e_mail['uid']}")
            print(f"email_date: {e_mail["email_date"]}")
            print(f"email_subject: {e_mail["subject"]}")
            print(f"llm_prediction: {llm_prediction}")
            print(f"llm_reasoning: {llm_reasoning}")            

            db_obj.save_transaction(e_mail=e_mail, llm_reasoning=llm_reasoning, llm_prediction=llm_prediction, account_id=account_id)
            print("Transaction stored to DB")
            
        elif llm_prediction["transaction_flag"] == False:
            print("Skipping non-transaction")
            print(f"from_address: {e_mail["from_address"]}")
            print(f"email_subject: {e_mail["subject"]}")

        print("-" * 100)        

        max_uid = max(max_uid, int(e_mail["uid"]))
        # Save updated UID
        with open(ckpt_file, "w") as f:
            f.write(str(max_uid))     

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=(argparse.RawDescriptionHelpFormatter)
    )
    parser.add_argument(
        "--email_host", 
        help="Email Host (IMAP Server Address)", 
        required=True
        )
    parser.add_argument(
        "--email_port", 
        help="Email Host (IMAP Server Address)", 
        required=True
        )
    parser.add_argument(
        "--username", 
        help="Email Account Username", 
        required=True
        )
    parser.add_argument(
        "--password", 
        help="Email Account Password", 
        required=True
        )
    parser.add_argument(
        "--folder", 
        help="Folder Name", 
        default="INBOX",
        required=True
        )
    parser.add_argument(
        "--ckpt_file", 
        help="Checkpoint File to store state", 
        required=True
        )
    parser.add_argument(
        "--transaction_rules", 
        help="Transaction Rules File", 
        required=True
        )
    parser.add_argument(
        "--db_file", 
        help="Duckdb database File", 
        required=True
        )
    parser.add_argument(
        "--prompt_file", 
        help="Prompt File", 
        required=True
        )    
    args = parser.parse_args()

    transactsync(args.email_host, args.email_port, args.username, args.password, args.folder, args.ckpt_file, args.transaction_rules, args.db_file, args.prompt_file)
