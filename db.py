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


@st.cache_data(ttl=60)
def get_clients() -> list:
    rows = _get_client().table("clients").select("name").eq("active", True).order("name").execute()
    return [row["name"] for row in rows.data]


def add_client(name: str):
    _get_client().table("clients").insert({"name": name}).execute()
    get_clients.clear()


def remove_client(name: str):
    _get_client().table("clients").update({"active": False}).eq("name", name).execute()
    get_clients.clear()


@st.cache_data(ttl=60)
def get_vehicles() -> list:
    rows = _get_client().table("vehicles").select("number").eq("active", True).order("number").execute()
    return [row["number"] for row in rows.data]


def add_vehicle(number: str):
    _get_client().table("vehicles").insert({"number": number}).execute()
    get_vehicles.clear()


def remove_vehicle(number: str):
    _get_client().table("vehicles").update({"active": False}).eq("number", number).execute()
    get_vehicles.clear()
