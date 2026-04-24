import streamlit as st
from google.oauth2.service_account import Credentials
from config import SCOPES


@st.cache_resource
def get_credentials():
    info = dict(st.secrets["google_service_account"])
    info["private_key"] = info["private_key"].replace("\\n", "\n")
    return Credentials.from_service_account_info(info, scopes=SCOPES)
