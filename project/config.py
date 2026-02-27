import os
from dotenv import load_dotenv

load_dotenv()

INTACCT_TOKEN = os.getenv("INTACCT_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {INTACCT_TOKEN}",
    "Content-Type": "application/json"
}
