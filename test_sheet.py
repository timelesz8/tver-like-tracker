import gspread
from google.oauth2.service_account import Credentials

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=scope
)

client = gspread.authorize(creds)

sheet = client.open("スプレッドシート名").sheet1

sheet.update("A1", "test")

print("success")