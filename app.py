import streamlit as st
from datetime import datetime

from config import DRIVERS
from auth import get_credentials
from drive import upload_image
from sheets import append_trip


def init_state():
    st.session_state.setdefault("phase", "start")
    st.session_state.setdefault("trip", {})


def trip_id(emp_id: str) -> str:
    return f"{emp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def camera_block(label: str, key: str):
    st.markdown(f"**{label}**")
    return st.camera_input("", key=key, label_visibility="collapsed")


def show_start_form():
    st.title("🚗 Zippi Trip Tracker")
    st.subheader("Start Trip")

    driver_name = st.selectbox("Driver Name", list(DRIVERS.keys()))
    emp_id = DRIVERS[driver_name]
    st.caption(f"Employee ID: **{emp_id}**  |  Date: **{datetime.today().strftime('%d %b %Y')}**")

    st.divider()
    start_km = st.number_input("Start Odometer (km)", min_value=0, step=1, format="%d")

    st.divider()
    st.subheader("📸 Start Photos")
    left = camera_block("Left Side of Vehicle", "start_left")
    right = camera_block("Right Side of Vehicle", "start_right")
    odo = camera_block("Odometer", "start_odo")

    st.divider()
    if st.button("▶  Start Trip", use_container_width=True, type="primary"):
        missing = [n for n, f in [("Left side", left), ("Right side", right), ("Odometer", odo)] if not f]
        if missing:
            st.warning(f"Please capture: {', '.join(missing)}")
        else:
            st.session_state["trip"] = {
                "trip_id": trip_id(emp_id),
                "driver_name": driver_name,
                "emp_id": emp_id,
                "date": datetime.today().strftime("%Y-%m-%d"),
                "start_time": datetime.now().strftime("%H:%M:%S"),
                "start_km": start_km,
                "start_left": left.getvalue(),
                "start_right": right.getvalue(),
                "start_odo": odo.getvalue(),
            }
            st.session_state["phase"] = "end"
            st.rerun()


def show_end_form():
    trip = st.session_state["trip"]

    st.title("🚗 Zippi Trip Tracker")
    st.success(
        f"Trip in progress — {trip['driver_name']} ({trip['emp_id']})\n\n"
        f"Started at **{trip['start_time']}** | Start KM: **{trip['start_km']}**"
    )

    st.subheader("End Trip")
    end_km = st.number_input("End Odometer (km)", min_value=0, step=1, format="%d")

    st.divider()
    st.subheader("📸 End Photos")
    left = camera_block("Left Side of Vehicle", "end_left")
    right = camera_block("Right Side of Vehicle", "end_right")
    odo = camera_block("Odometer", "end_odo")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        submit = st.button("✅  Submit Trip", use_container_width=True, type="primary")
    with col2:
        cancel = st.button("✖  Cancel Trip", use_container_width=True)

    if cancel:
        st.session_state["phase"] = "start"
        st.session_state["trip"] = {}
        st.rerun()

    if submit:
        missing = [n for n, f in [("Left side", left), ("Right side", right), ("Odometer", odo)] if not f]
        if missing:
            st.warning(f"Please capture: {', '.join(missing)}")
            return
        if end_km <= trip["start_km"]:
            st.warning("End odometer must be greater than start odometer.")
            return

        with st.spinner("Uploading photos and saving trip..."):
            creds = get_credentials()
            end_time = datetime.now().strftime("%H:%M:%S")

            def upload(data, name):
                return upload_image(creds, data, f"{trip['trip_id']}_{name}.jpg")

            row = {
                "Trip ID": trip["trip_id"],
                "Driver Name": trip["driver_name"],
                "Employee ID": trip["emp_id"],
                "Date": trip["date"],
                "Start Time": trip["start_time"],
                "End Time": end_time,
                "Start Odometer (km)": trip["start_km"],
                "End Odometer (km)": end_km,
                "Distance (km)": end_km - trip["start_km"],
                "Start - Left Photo": upload(trip["start_left"], "start_left"),
                "Start - Right Photo": upload(trip["start_right"], "start_right"),
                "Start - Odometer Photo": upload(trip["start_odo"], "start_odo"),
                "End - Left Photo": upload(left.getvalue(), "end_left"),
                "End - Right Photo": upload(right.getvalue(), "end_right"),
                "End - Odometer Photo": upload(odo.getvalue(), "end_odo"),
                "Submitted At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            append_trip(creds, row)

        st.balloons()
        st.success(f"Trip saved! Distance: {end_km - trip['start_km']} km")
        st.session_state["phase"] = "start"
        st.session_state["trip"] = {}


def main():
    st.set_page_config(page_title="Zippi Trip Tracker", page_icon="🚗", layout="centered")
    init_state()

    if st.session_state["phase"] == "start":
        show_start_form()
    else:
        show_end_form()


if __name__ == "__main__":
    main()
