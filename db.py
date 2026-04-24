import streamlit as st
from supabase import create_client


@st.cache_resource
def _get_client():
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["service_role_key"],
    )


@st.cache_data(ttl=60)
def get_drivers() -> dict:
    rows = _get_client().table("drivers").select("name, emp_id").eq("active", True).order("name").execute()
    return {row["name"]: row["emp_id"] for row in rows.data}


def add_driver(name: str, emp_id: str):
    _get_client().table("drivers").insert({"name": name, "emp_id": emp_id}).execute()
    get_drivers.clear()


def remove_driver(emp_id: str):
    _get_client().table("drivers").update({"active": False}).eq("emp_id", emp_id).execute()
    get_drivers.clear()
