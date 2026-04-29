import streamlit as st
from db import (
    get_drivers, add_driver, remove_driver,
    get_clients, add_client, remove_client,
    get_vehicles, add_vehicle, remove_vehicle,
)


def check_password() -> bool:
    if st.session_state.get("admin_auth"):
        return True

    st.subheader("Admin Login")
    pwd = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True, type="primary"):
        if pwd == st.secrets["admin"]["password"]:
            st.session_state["admin_auth"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False


def show_drivers():
    st.subheader("Drivers")
    with st.form("add_driver", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Full Name")
        emp_id = col2.text_input("Employee ID")
        if st.form_submit_button("Add Driver", use_container_width=True, type="primary"):
            if not name or not emp_id:
                st.warning("Both fields are required.")
            else:
                add_driver(name.strip(), emp_id.strip().upper())
                st.success(f"Added {name}")
                st.rerun()

    drivers = get_drivers()
    if not drivers:
        st.info("No drivers yet.")
        return
    for name, emp_id in drivers.items():
        col1, col2, col3 = st.columns([4, 2, 1])
        col1.write(name)
        col2.write(emp_id)
        if col3.button("Remove", key=f"drv_{emp_id}"):
            remove_driver(emp_id)
            st.rerun()


def show_clients():
    st.subheader("Clients")
    with st.form("add_client", clear_on_submit=True):
        name = st.text_input("Client Name")
        if st.form_submit_button("Add Client", use_container_width=True, type="primary"):
            if not name:
                st.warning("Client name is required.")
            else:
                add_client(name.strip())
                st.success(f"Added {name}")
                st.rerun()

    clients = get_clients()
    if not clients:
        st.info("No clients yet.")
        return
    for name in clients:
        col1, col2 = st.columns([5, 1])
        col1.write(name)
        if col2.button("Remove", key=f"cli_{name}"):
            remove_client(name)
            st.rerun()


def show_vehicles():
    st.subheader("Vehicles")
    with st.form("add_vehicle", clear_on_submit=True):
        number = st.text_input("Vehicle Number")
        if st.form_submit_button("Add Vehicle", use_container_width=True, type="primary"):
            if not number:
                st.warning("Vehicle number is required.")
            else:
                add_vehicle(number.strip().upper())
                st.success(f"Added {number}")
                st.rerun()

    vehicles = get_vehicles()
    if not vehicles:
        st.info("No vehicles yet.")
        return
    for number in vehicles:
        col1, col2 = st.columns([5, 1])
        col1.write(number)
        if col2.button("Remove", key=f"veh_{number}"):
            remove_vehicle(number)
            st.rerun()


def main():
    st.set_page_config(page_title="Admin – Zippi", page_icon="⚙️", layout="centered")
    st.title("⚙️ Admin")

    if not check_password():
        return

    if st.button("Logout", type="secondary"):
        st.session_state["admin_auth"] = False
        st.rerun()

    st.divider()
    show_drivers()
    st.divider()
    show_clients()
    st.divider()
    show_vehicles()


main()
