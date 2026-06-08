import streamlit as st
import pandas as pd
from billing_engine import get_all_billing_rules, add_billing_rule, update_billing_rule
from db import get_clients


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


def show_add_rule(clients: list):
    with st.expander("➕ Add New Rule"):
        with st.form("add_billing_rule", clear_on_submit=True):
            col1, col2 = st.columns(2)
            client_name  = col1.selectbox("Client", clients)
            billing_type = col2.selectbox("Billing Type", ["FLAT", "SLAB"])

            if billing_type == "SLAB":
                col3, col4 = st.columns(2)
                min_km = col3.number_input("Min KM", min_value=0.0, step=1.0)
                max_km = col4.number_input("Max KM", min_value=0.0, step=1.0)
            else:
                min_km = max_km = None

            amount = st.number_input("Amount (₹)", min_value=0.0, step=50.0)

            if st.form_submit_button("Add Rule", use_container_width=True, type="primary"):
                if not client_name:
                    st.warning("Client name is required.")
                elif billing_type == "SLAB" and max_km <= min_km:
                    st.warning("Max KM must be greater than Min KM.")
                elif amount <= 0:
                    st.warning("Amount must be greater than zero.")
                else:
                    rule = {
                        "client_name":  client_name,
                        "billing_type": billing_type,
                        "amount":       amount,
                    }
                    if billing_type == "SLAB":
                        rule["min_km"] = min_km
                        rule["max_km"] = max_km
                    add_billing_rule(rule)
                    st.success(f"Rule added for {client_name}.")
                    st.rerun()


def show_rules_table():
    rules = get_all_billing_rules()
    if not rules:
        st.info("No billing rules yet. Add one above.")
        return

    df_original = pd.DataFrame(rules)
    # Reorder columns for display
    display_cols = ["id", "client_name", "billing_type", "min_km", "max_km", "amount", "active", "created_at"]
    display_cols = [c for c in display_cols if c in df_original.columns]
    df_original = df_original[display_cols]

    df_edited = st.data_editor(
        df_original,
        column_config={
            "id":           st.column_config.NumberColumn("ID",           disabled=True),
            "client_name":  st.column_config.TextColumn("Client",         disabled=True),
            "billing_type": st.column_config.SelectboxColumn("Type",      options=["FLAT", "SLAB"]),
            "min_km":       st.column_config.NumberColumn("Min KM"),
            "max_km":       st.column_config.NumberColumn("Max KM"),
            "amount":       st.column_config.NumberColumn("Amount (₹)",   format="₹%.2f"),
            "active":       st.column_config.CheckboxColumn("Active"),
            "created_at":   st.column_config.TextColumn("Created",        disabled=True),
        },
        use_container_width=True,
        hide_index=True,
    )

    if st.button("💾 Save Changes", type="primary"):
        saved = 0
        for _, row in df_edited.iterrows():
            orig_rows = df_original[df_original["id"] == row["id"]]
            if orig_rows.empty:
                continue
            orig = orig_rows.iloc[0]
            changed = {
                k: row[k]
                for k in ["billing_type", "min_km", "max_km", "amount", "active"]
                if k in row and row[k] != orig[k]
            }
            if changed:
                update_billing_rule(int(row["id"]), changed)
                saved += 1
        if saved:
            st.success(f"Saved {saved} change(s).")
        else:
            st.info("No changes detected.")
        st.rerun()


def main():
    st.set_page_config(page_title="Billing Rules – Zippi", page_icon="💰", layout="centered")
    st.title("💰 Billing Rules")

    if not check_password():
        return

    if st.button("Logout", type="secondary"):
        st.session_state["admin_auth"] = False
        st.rerun()

    st.divider()

    clients = get_clients()
    if not clients:
        st.warning("No clients configured. Add clients in the Admin page first.")
        return

    show_add_rule(clients)
    st.divider()
    show_rules_table()


main()
