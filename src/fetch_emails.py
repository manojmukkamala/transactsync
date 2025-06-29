import imaplib
import email
from bs4 import BeautifulSoup
from email.header import decode_header
from email.utils import parsedate_to_datetime

class EmailHandler:

    def __init__(self, host, port, username, password, folder):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.folder = folder

    def imap_bridge(self):
        """
        Connect to an email account using the IMAP protocol.

        Returns:
            imaplib.IMAP4: An instance of the IMAP4 class representing the connection to the email account.
        """
        try:
            # Connect to the IMAP server
            self.imapb = imaplib.IMAP4(self.host, self.port)
            # Login to the account
            self.imapb.login(self.username, self.password)
            return self.imapb
        except Exception as e:
            raise RuntimeError(f"Failed to connect to email account: {e}")
    
    def get_email_uids(self, last_seen_uid=None):
        """
        Retrieve UIDs of emails in a folder. If last_seen_uid is given, only fetch newer ones.

        Args:
            last_seen_uid: last_seen_uid

        Returns:
            list: A list containing all email index numbers in the specified folder.
        """
        try:
            if not hasattr(self, 'imapb') or self.imapb is None:
                raise RuntimeError("IMAP connection not established. Call imap_bridge first.")
            
            status, _ = self.imapb.select(f'"{self.folder}"')
            if status != "OK":
                raise Exception(f"Failed to select folder: {self.folder}")

            # Search from UID+1 to newest
            if last_seen_uid:
                criteria = f"UID {int(last_seen_uid) + 1}:*"
            else:
                criteria = "ALL"

            status, messages = self.imapb.uid("search", None, criteria)
            if status != "OK":
                raise Exception("Failed to search for emails")

            return messages[0].split()
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve email UIDs: {e}")
    
    def get_emails(self, last_seen_uid=None):
        """
        Retrieve emails newer than last_seen_uid.

        Args:
            last_seen_uid (int): UID of the last seen email.

        Returns:
            list: A list of dictionaries containing email details.
        """
        try:
            self.imapb = self.imap_bridge()
            uids = self.get_email_uids(last_seen_uid)
            
            e_mails = []
            for uid in uids:
                status, msg_data = self.imapb.uid("fetch", uid, "(RFC822)")
                if status != "OK":
                    print(f"Failed to fetch email UID {uid}")
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject, encoding = decode_header(msg["Subject"])[0]
                subject = subject.decode(encoding or "utf-8") if isinstance(subject, bytes) else subject

                # Decode date
                raw_date = msg["Date"]
                parsed_date = parsedate_to_datetime(raw_date)
                email_date = parsed_date.isoformat() if parsed_date else raw_date

                # Decode from
                from_address = msg["From"]

                # Decode to
                to_address = msg["To"]

                # Extract body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                        elif content_type == "text/html":
                            html = part.get_payload(decode=True).decode(errors="ignore")
                            soup = BeautifulSoup(html, "html.parser")
                            body = soup.get_text()
                            break
                else:
                    content_type = msg.get_content_type()
                    if content_type == "text/html":
                        html = msg.get_payload(decode=True).decode(errors="ignore")
                        soup = BeautifulSoup(html, "html.parser")
                        body = soup.get_text()
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")

                e_mails.append({
                    "uid": uid,
                    "subject": subject,
                    "email_date": email_date,
                    "from_address": from_address,
                    "to_address": to_address,
                    "body": body
                })

            self.imapb.logout()
            return e_mails
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve emails: {e}")
