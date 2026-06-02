import streamlit as st
import pandas as pd
from datetime import date
from zoneinfo import ZoneInfo

from auth import get_credentials
from db import get_drivers
from sheets import (
    get_master_roster, add_master_entry, update_master_entry, delete_master_entry,
    get_daily_roster, write_daily_roster, add_daily_entry, delete_daily_entry,
)
from config import MASTER_ROSTER_COLUMNS, ROSTER_COLUMNS

IST = ZoneInfo("Asia/Kolkata")

EXCEL_COLUMN_MAP = {
    "Emp name": "Client Employee Name",
    "Location": "Location",
    "Mobile": "Mobile",
    "Week Offs": "Week Offs",
    "RT No": "RT No",
    "Login": "Login Time",
    "Login Driver": "Login Driver Name",
    "Logout": "Logout Time",
    "Logout Driver": "Logout Driver Name",
    "Report time": "Report Time",
}

SAMPLE_CSV = """\
RT No,Emp name,Location,Mobile,Week Offs,Report Time,Login,Login Driver,Logout,Logout Driver
RT-01,Ravi Kumar,MG Road - Gate 2,9876543210,Sunday,08:45,09:00,Ramesh Kumar,18:30,Suresh Patel
RT-02,Priya Nair,Whitefield Office,9876543211,Wednesday,08:30,08:45,Mahesh Singh,18:00,Dinesh Rao
RT-03,Arjun Mehta,Electronic City,9876543212,Sunday,08:00,08:15,Ramesh Kumar,17:30,Mahesh Singh
"""


def check_password() -> bool:
    if st.session_state.get("admin_auth"):
        return True
    st.subheader("Login")
    pwd = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True, type="primary"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state["admin_auth"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False


def _driver_options(drivers: dict) -> list[str]:
    return ["— none —"] + list(drivers.keys())


def _entry_form(form_key: str, drivers: dict, prefill: dict | None = None) -> dict | None:
    p = prefill or {}
    driver_names = list(drivers.keys())
    options = _driver_options(drivers)

    def driver_index(name):
        return options.index(name) if name in options else 0

    with st.form(form_key, clear_on_submit=True):
        col1, col2 = st.columns(2)
        rt_no = col1.text_input("RT No", value=p.get("RT No", ""))
        location = col2.text_input("Location", value=p.get("Location", ""))

        col3, col4 = st.columns(2)
        emp_name = col3.text_input("Client Employee Name", value=p.get("Client Employee Name", ""))
        mobile = col4.text_input("Mobile", value=p.get("Mobile", ""))

        col5, col6 = st.columns(2)
        week_offs = col5.text_input("Week Offs (e.g. Sunday)", value=p.get("Week Offs", ""))
        report_time = col6.text_input("Report Time (HH:MM)", value=p.get("Report Time", ""))

        st.markdown("**Login**")
        col7, col8, col9 = st.columns([2, 2, 2])
        login_time = col7.text_input("Login Time (HH:MM)", value=p.get("Login Time", ""))
        login_driver = col8.selectbox(
            "Login Driver", options, index=driver_index(p.get("Login Driver Name", ""))
        )
        login_mobile = col9.text_input("Login Driver Mobile (auto)", value="", disabled=True)

        st.markdown("**Logout**")
        col10, col11 = st.columns([2, 2])
        logout_time = col10.text_input("Logout Time (HH:MM)", value=p.get("Logout Time", ""))
        logout_driver = col11.selectbox(
            "Logout Driver", options, index=driver_index(p.get("Logout Driver Name", ""))
        )

        submitted = st.form_submit_button(
            "Save Entry" if prefill else "Add Entry",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        if not emp_name or not rt_no:
            st.warning("RT No and Client Employee Name are required.")
            return None
        login_emp_id = drivers.get(login_driver, "") if login_driver != "— none —" else ""
        logout_emp_id = drivers.get(logout_driver, "") if logout_driver != "— none —" else ""
        return {
            "RT No": rt_no.strip(),
            "Client Employee Name": emp_name.strip(),
            "Location": location.strip(),
            "Mobile": mobile.strip(),
            "Week Offs": week_offs.strip(),
            "Report Time": report_time.strip(),
            "Login Time": login_time.strip(),
            "Login Driver Name": login_driver if login_driver != "— none —" else "",
            "Login Driver Employee ID": login_emp_id,
            "Logout Time": logout_time.strip(),
            "Logout Driver Name": logout_driver if logout_driver != "— none —" else "",
            "Logout Driver Employee ID": logout_emp_id,
        }
    return None


def show_master_roster(creds, drivers):
    st.subheader("Master Roster")

    editing = st.session_state.get("master_edit_row")

    if editing:
        st.info(f"Editing entry: **{editing.get('Client Employee Name')}** (RT {editing.get('RT No')})")
        result = _entry_form("edit_master_form", drivers, prefill=editing)
        if result:
            update_master_entry(creds, editing["_row"], result)
            st.session_state.pop("master_edit_row", None)
            st.success("Entry updated.")
            st.rerun()
        if st.button("Cancel Edit"):
            st.session_state.pop("master_edit_row", None)
            st.rerun()
    else:
        with st.expander("➕ Add New Entry", expanded=False):
            result = _entry_form("add_master_form", drivers)
            if result:
                add_master_entry(creds, result)
                st.success(f"Added {result['Client Employee Name']}.")
                st.rerun()

    st.divider()

    rows = get_master_roster(creds)
    if not rows:
        st.info("No entries yet. Add one above or upload from Excel.")
    else:
        for row in rows:
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
            col1.write(f"**{row.get('RT No', '')}**")
            col2.write(row.get("Client Employee Name", ""))
            col3.write(f"↑ {row.get('Login Time', '')}  {row.get('Login Driver Name', '')}")
            col4.write(f"↓ {row.get('Logout Time', '')}  {row.get('Logout Driver Name', '')}")
            btn_col1, btn_col2 = col5.columns(2)
            if btn_col1.button("✏️", key=f"edit_m_{row['_row']}"):
                st.session_state["master_edit_row"] = row
                st.rerun()
            if btn_col2.button("🗑️", key=f"del_m_{row['_row']}"):
                delete_master_entry(creds, row["_row"])
                st.rerun()

    st.divider()

    with st.expander("📂 Upload from Excel / CSV"):
        st.download_button(
            "⬇️ Download sample CSV",
            data=SAMPLE_CSV,
            file_name="roster_sample.csv",
            mime="text/csv",
        )
        st.caption(
            "Columns: RT No · Emp name · Location · Mobile · Week Offs · "
            "Report Time · Login · Login Driver · Logout · Logout Driver"
        )
        st.divider()
        uploaded = st.file_uploader(
            "Upload your roster Excel or CSV",
            type=["xlsx", "xls", "csv"],
            key="master_upload",
        )
        if uploaded:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)

            # Rename columns from old Excel format
            df = df.rename(columns=EXCEL_COLUMN_MAP)

            # Handle old Excel files with two duplicate "Driver" columns
            # (pandas auto-renames the second one to "Driver.1")
            if "Driver" in df.columns and "Login Driver Name" not in df.columns:
                df = df.rename(columns={"Driver": "Login Driver Name"})
            if "Driver.1" in df.columns and "Logout Driver Name" not in df.columns:
                df = df.rename(columns={"Driver.1": "Logout Driver Name"})

            display_cols = [c for c in MASTER_ROSTER_COLUMNS if c in df.columns]
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)

            if st.button(f"Import {len(df)} rows into Master Roster", type="primary"):
                imported = 0
                for _, r in df.iterrows():
                    row_dict = {col: str(r.get(col, "")) for col in MASTER_ROSTER_COLUMNS}
                    # Auto-fill Employee IDs from driver name if found
                    login_name = row_dict.get("Login Driver Name", "")
                    row_dict["Login Driver Employee ID"] = drivers.get(login_name, "")
                    logout_name = row_dict.get("Logout Driver Name", "")
                    row_dict["Logout Driver Employee ID"] = drivers.get(logout_name, "")
                    add_master_entry(creds, row_dict)
                    imported += 1
                st.success(f"Imported {imported} entries.")
                st.rerun()


def _week_off_matches(week_offs: str, day_name: str) -> bool:
    if not week_offs:
        return False
    return day_name[:3].lower() in week_offs.lower()


def show_daily_roster(creds, drivers):
    today_ist = date.today()
    selected = st.date_input("Date", value=today_ist)
    date_str = selected.strftime("%Y-%m-%d")
    day_name = selected.strftime("%A")
    st.caption(f"**{day_name}**")

    st.divider()

    existing = get_daily_roster(creds, date_str)

    col_gen, col_info = st.columns([2, 3])
    with col_gen:
        if st.button("⚡ Generate from Master", use_container_width=True, type="primary"):
            if existing:
                st.session_state["confirm_overwrite"] = date_str
            else:
                _do_generate(creds, date_str, day_name)
                st.rerun()

    if st.session_state.get("confirm_overwrite") == date_str:
        st.warning(f"{len(existing)} entries already exist for {date_str}. Overwrite?")
        c1, c2 = st.columns(2)
        if c1.button("Yes, overwrite", type="primary"):
            st.session_state.pop("confirm_overwrite", None)
            _do_generate(creds, date_str, day_name)
            st.rerun()
        if c2.button("Cancel"):
            st.session_state.pop("confirm_overwrite", None)
            st.rerun()

    st.subheader(f"Roster for {date_str}")

    existing = get_daily_roster(creds, date_str)
    if not existing:
        st.info("No entries yet. Generate from master or add manually below.")
    else:
        for row in existing:
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
            col1.write(f"**{row.get('RT No', '')}**")
            col2.write(row.get("Client Employee Name", ""))
            col3.write(f"↑ {row.get('Login Time', '')}  {row.get('Login Driver Name', '')}")
            col4.write(f"↓ {row.get('Logout Time', '')}  {row.get('Logout Driver Name', '')}")
            if col5.button("🗑️", key=f"del_d_{row['_row']}"):
                delete_daily_entry(creds, row["_row"])
                st.rerun()

    st.divider()

    with st.expander("➕ Add / Override Entry for This Date"):
        result = _entry_form("add_daily_form", drivers)
        if result:
            result["Date"] = date_str
            add_daily_entry(creds, result)
            st.success(f"Added {result['Client Employee Name']} to {date_str} roster.")
            st.rerun()


def _do_generate(creds, date_str: str, day_name: str):
    master = get_master_roster(creds)
    rows = []
    skipped = 0
    for entry in master:
        if _week_off_matches(str(entry.get("Week Offs", "")), day_name):
            skipped += 1
            continue
        row = {col: entry.get(col, "") for col in MASTER_ROSTER_COLUMNS}
        row["Date"] = date_str
        rows.append(row)
    write_daily_roster(creds, date_str, rows)
    msg = f"Generated {len(rows)} entries for {date_str}."
    if skipped:
        msg += f" Skipped {skipped} on week off."
    st.success(msg)


def main():
    st.set_page_config(page_title="Roster – Zippi", page_icon="📋", layout="centered")
    st.title("📋 Roster Management")

    if not check_password():
        return

    if st.button("Logout", type="secondary"):
        st.session_state["admin_auth"] = False
        st.rerun()

    st.divider()

    creds = get_credentials()
    drivers = get_drivers()

    tab_master, tab_daily = st.tabs(["📋 Master Roster", "📅 Daily Roster"])

    with tab_master:
        show_master_roster(creds, drivers)

    with tab_daily:
        show_daily_roster(creds, drivers)


main()
