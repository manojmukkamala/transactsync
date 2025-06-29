# transactsync
A privacy focussed expenses logging tool

### Example Usage:

```
- uv sync
- uv run src/main.py --email_host="127.0.0.1" --email_port=1143 --username="user@email.com" --password="pass1234" --folder="INBOX" --ckpt="./last_uid.txt" --transaction_rules="./transaction_rules.yaml" --transactions_db="./finances.db" --transactions_table="transactions"
```