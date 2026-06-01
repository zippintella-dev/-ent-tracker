import gspread
from config import SHEET_ID, SHEET_NAME


def append_trip(creds, row: dict):
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    sheet = spreadsheet.worksheet(SHEET_NAME)
    sheet.append_row(list(row.values()), value_input_option="USER_ENTERED")
    print(f"✅ Written to: {spreadsheet.title} → {sheet.title} (row ~{sheet.row_count})")


def update_trip_end(creds, trip_id: str, end_data: dict):
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    cell = sheet.find(trip_id, in_column=1)
    if not cell:
        raise ValueError(f"Trip {trip_id} not found in sheet")
    headers = sheet.row_values(1)
    for col_name, value in end_data.items():
        if col_name in headers:
            sheet.update_cell(cell.row, headers.index(col_name) + 1, value)
