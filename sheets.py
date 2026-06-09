import gspread
from config import SHEET_ID, SHEET_NAME, ROSTER_SHEET_NAME, MASTER_ROSTER_SHEET_NAME, MASTER_ROSTER_COLUMNS, ROSTER_COLUMNS


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


# ── Master Roster ────────────────────────────────────────────────────────────

def _open_master(creds):
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(MASTER_ROSTER_SHEET_NAME)


def get_master_roster(creds) -> list[dict]:
    sheet = _open_master(creds)
    rows = sheet.get_all_records()
    for i, row in enumerate(rows):
        row["_row"] = i + 2  # 1-based, row 1 is header
    return rows


def add_master_entry(creds, row: dict):
    sheet = _open_master(creds)
    sheet.append_row(
        [row.get(col, "") for col in MASTER_ROSTER_COLUMNS],
        value_input_option="RAW",
    )


def add_master_entries_batch(creds, rows: list[dict]):
    """Write multiple master roster rows in a single API call."""
    sheet = _open_master(creds)
    values = [[row.get(col, "") for col in MASTER_ROSTER_COLUMNS] for row in rows]
    sheet.append_rows(values, value_input_option="RAW")


def update_master_entry(creds, row_number: int, row: dict):
    sheet = _open_master(creds)
    sheet.update(
        f"A{row_number}",
        [[row.get(col, "") for col in MASTER_ROSTER_COLUMNS]],
        value_input_option="RAW",
    )


def delete_master_entry(creds, row_number: int):
    _open_master(creds).delete_rows(row_number)


# ── Daily Roster ─────────────────────────────────────────────────────────────

def _open_daily(creds):
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(ROSTER_SHEET_NAME)


def _normalize_date(value: str) -> str:
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(value).strip()


def get_daily_roster(creds, date_str: str) -> list[dict]:
    sheet = _open_daily(creds)
    rows = sheet.get_all_records()
    result = []
    for i, row in enumerate(rows):
        if _normalize_date(str(row.get("Date", ""))) == date_str:
            row["_row"] = i + 2
            result.append(row)
    return result


def write_daily_roster(creds, date_str: str, rows: list[dict]):
    sheet = _open_daily(creds)
    all_rows = sheet.get_all_values()
    to_delete = [
        i + 2
        for i, r in enumerate(all_rows[1:])
        if r and _normalize_date(r[0]) == date_str
    ]
    for row_number in reversed(to_delete):
        sheet.delete_rows(row_number)
    if not rows:
        return
    # Calculate next row from the initial read minus deleted rows — avoids
    # a second get_all_values() API call.
    next_row = max(len(all_rows) - len(to_delete) + 1, 2)
    values = [[row.get(col, "") for col in ROSTER_COLUMNS] for row in rows]
    sheet.update(f"A{next_row}", values, value_input_option="RAW")


def add_daily_entry(creds, row: dict):
    sheet = _open_daily(creds)
    last_row = len(sheet.get_all_values())
    next_row = max(last_row + 1, 2)
    sheet.update(
        f"A{next_row}",
        [[row.get(col, "") for col in ROSTER_COLUMNS]],
        value_input_option="RAW",
    )


def update_daily_entry(creds, row_number: int, row: dict):
    sheet = _open_daily(creds)
    sheet.update(
        f"A{row_number}",
        [[row.get(col, "") for col in ROSTER_COLUMNS]],
        value_input_option="RAW",
    )


def replace_route_driver(
    creds,
    date_str: str,
    rt_no: str,
    slot: str,
    new_driver_name: str,
    new_driver_emp_id: str,
) -> int:
    """Replace login/logout driver on every row matching date + RT No.
    slot: 'login', 'logout', or 'both'. Returns number of rows updated."""
    sheet = _open_daily(creds)
    all_rows = sheet.get_all_records()

    updates = []
    for i, row in enumerate(all_rows):
        if _normalize_date(str(row.get("Date", ""))) != date_str:
            continue
        if str(row.get("RT No", "")).strip() != rt_no.strip():
            continue
        updated = dict(row)
        if slot in ("login", "both"):
            updated["Login Driver Name"]        = new_driver_name
            updated["Login Driver Employee ID"] = new_driver_emp_id
        if slot in ("logout", "both"):
            updated["Logout Driver Name"]        = new_driver_name
            updated["Logout Driver Employee ID"] = new_driver_emp_id
        updates.append((i + 2, updated))

    for row_number, row_data in updates:
        sheet.update(
            f"A{row_number}",
            [[row_data.get(col, "") for col in ROSTER_COLUMNS]],
            value_input_option="RAW",
        )
    return len(updates)


def delete_daily_entry(creds, row_number: int):
    _open_daily(creds).delete_rows(row_number)
