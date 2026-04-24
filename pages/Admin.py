import streamlit as st
from db import get_drivers, add_driver, remove_driver


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


def show_add_form():
    st.subheader("Add Driver")
    with st.form("add_driver", clear_on_submit=True):
        name = st.text_input("Full Name")
        emp_id = st.text_input("Employee ID")
        if st.form_submit_button("Add Driver", use_container_width=True, type="primary"):
            if not name or not emp_id:
                st.warning("Both fields are required.")
            else:
                add_driver(name.strip(), emp_id.strip().upper())
                st.success(f"Added {name}")
                st.rerun()


def show_driver_list():
    st.subheader("Current Drivers")
    drivers = get_drivers()
    if not drivers:
        st.info("No drivers yet.")
        return

    for name, emp_id in drivers.items():
        col1, col2, col3 = st.columns([4, 2, 1])
        col1.write(name)
        col2.write(emp_id)
        if col3.button("Remove", key=emp_id):
            remove_driver(emp_id)
            st.rerun()


def main():
    st.set_page_config(page_title="Admin – Zippi", page_icon="⚙️", layout="centered")
    st.title("⚙️ Driver Management")

    if not check_password():
        return

    if st.button("Logout", type="secondary"):
        st.session_state["admin_auth"] = False
        st.rerun()

    st.divider()
    show_add_form()
    st.divider()
    show_driver_list()


main()
