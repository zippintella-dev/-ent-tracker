import streamlit as st
from google.oauth2.service_account import Credentials
from config import SCOPES


@st.cache_resource
def get_credentials():
    return Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=SCOPES,
    )
