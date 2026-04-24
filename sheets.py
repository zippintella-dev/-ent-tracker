import gspread
import streamlit as st
from config import SHEET_ID, SHEET_NAME


@st.cache_resource
def _get_sheet(_creds):
    client = gspread.authorize(_creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)


def append_trip(creds, row: dict):
    sheet = _get_sheet(creds)
    sheet.append_row(list(row.values()), value_input_option="USER_ENTERED")
