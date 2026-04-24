import streamlit as st
from google.oauth2.service_account import Credentials
from config import SCOPES


@st.cache_resource
def get_credentials():
    info = dict(st.secrets["google_service_account"])
    key = info["private_key"].replace("\\n", "\n")
    key = key.replace("BEGIN RSA PRIVATE KEY", "BEGIN PRIVATE KEY")
    key = key.replace("END RSA PRIVATE KEY", "END PRIVATE KEY")
    info["private_key"] = key
    return Credentials.from_service_account_info(info, scopes=SCOPES)
