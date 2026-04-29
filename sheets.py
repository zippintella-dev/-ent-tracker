import gspread
from config import SHEET_ID, SHEET_NAME


def append_trip(creds, row: dict):
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    sheet = spreadsheet.worksheet(SHEET_NAME)
    sheet.append_row(list(row.values()), value_input_option="USER_ENTERED")
    print(f"✅ Written to: {spreadsheet.title} → {sheet.title} (row ~{sheet.row_count})")
