import streamlit as st
from supabase import create_client


@st.cache_resource
def _get_client():
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["service_role_key"],
    )


def upload_image(file_bytes: bytes, filename: str) -> str:
    client = _get_client()
    client.storage.from_("trip-photos").upload(
        path=filename,
        file=file_bytes,
        file_options={"content-type": "image/jpeg", "upsert": "true"},
    )
    return client.storage.from_("trip-photos").get_public_url(filename)
