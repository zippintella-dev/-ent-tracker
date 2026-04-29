import base64
import streamlit as st
from datetime import datetime
from streamlit_js_eval import get_geolocation

from auth import get_credentials
from storage import upload_image
from sheets import append_trip
from db import get_drivers


@st.cache_data
def _logo_b64() -> str:
    with open("logo.png", "rb") as f:
        return base64.b64encode(f.read()).decode()


def show_header():
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.5rem;">
        <div style="font-size:1.6rem;font-weight:700;">🚗 Zippi Trip Tracker</div>
        <img src="data:image/png;base64,{_logo_b64()}"
             style="width:58px;height:58px;object-fit:contain;border-radius:10px;flex-shrink:0;">
    </div>
    """, unsafe_allow_html=True)



def init_state():
    st.session_state.setdefault("phase", "start")
    st.session_state.setdefault("trip", {})
    st.session_state.setdefault("last_trip", {})


def trip_id(emp_id: str) -> str:
    return f"{emp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def camera_block(label: str, key: str):
    st.markdown(f"**{label}**")
    return st.camera_input("", key=key, label_visibility="collapsed")


def maps_link(loc) -> str:
    if not loc or "coords" not in loc:
        return "Not available"
    lat = loc["coords"]["latitude"]
    lng = loc["coords"]["longitude"]
    return f"https://maps.google.com/?q={lat},{lng}"


def show_start_form():
    show_header()
    st.subheader("Start Trip")

    location = get_geolocation()
    if location:
        st.caption("📍 Location captured")
    else:
        st.caption("📍 Waiting for location — allow access if prompted")

    drivers = get_drivers()
    driver_name = st.selectbox("Driver Name", list(drivers.keys()))
    emp_id = drivers[driver_name]
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
                "start_location": maps_link(location),
                "start_left": left.getvalue(),
                "start_right": right.getvalue(),
                "start_odo": odo.getvalue(),
            }
            st.session_state["phase"] = "end"
            st.rerun()


def show_end_form():
    trip = st.session_state["trip"]

    show_header()
    st.success(
        f"Trip in progress — {trip['driver_name']} ({trip['emp_id']})\n\n"
        f"Started at **{trip['start_time']}** | Start KM: **{trip['start_km']}**"
    )

    location = get_geolocation()
    if location:
        st.caption("📍 Location captured")
    else:
        st.caption("📍 Waiting for location — allow access if prompted")

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

        assert left and right and odo  # guaranteed by missing check above

        try:
            with st.spinner("Uploading photos and saving trip..."):
                creds = get_credentials()
                end_time = datetime.now().strftime("%H:%M:%S")
                distance = end_km - trip["start_km"]

                def upload(data, name):
                    return upload_image(data, f"{trip['trip_id']}_{name}.jpg")

                row = {
                    "Trip ID": trip["trip_id"],
                    "Driver Name": trip["driver_name"],
                    "Employee ID": trip["emp_id"],
                    "Date": trip["date"],
                    "Start Time": trip["start_time"],
                    "End Time": end_time,
                    "Start Odometer (km)": trip["start_km"],
                    "End Odometer (km)": end_km,
                    "Distance (km)": distance,
                    "Start Location": trip["start_location"],
                    "End Location": maps_link(location),
                    "Start - Left Photo": upload(trip["start_left"], "start_left"),
                    "Start - Right Photo": upload(trip["start_right"], "start_right"),
                    "Start - Odometer Photo": upload(trip["start_odo"], "start_odo"),
                    "End - Left Photo": upload(left.getvalue(), "end_left"),
                    "End - Right Photo": upload(right.getvalue(), "end_right"),
                    "End - Odometer Photo": upload(odo.getvalue(), "end_odo"),
                    "Submitted At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                append_trip(creds, row)
        except Exception as e:
            st.error(f"Failed to save trip: {e}")
            return

        st.session_state["last_trip"] = {
            "driver_name": trip["driver_name"],
            "date": trip["date"],
            "start_km": trip["start_km"],
            "end_km": end_km,
            "distance": distance,
        }
        st.session_state["phase"] = "saved"
        st.session_state["trip"] = {}
        st.rerun()


def show_saved_screen():
    last = st.session_state["last_trip"]

    show_header()
    st.balloons()
    st.success("✅ Trip Saved!")

    st.divider()
    st.markdown(f"**Driver:** {last['driver_name']}")
    st.markdown(f"**Date:** {last['date']}")
    st.markdown(f"**Distance:** {last['distance']} km")
    st.markdown(f"**Odometer:** {last['start_km']} → {last['end_km']} km")

    st.divider()
    if st.button("▶  Start Next Trip", use_container_width=True, type="primary"):
        st.session_state["phase"] = "start"
        st.session_state["last_trip"] = {}
        st.rerun()


def main():
    st.set_page_config(page_title="Zippi Trip Tracker", page_icon="🚗", layout="centered")
    init_state()

    phase = st.session_state["phase"]
    if phase == "start":
        show_start_form()
    elif phase == "end":
        show_end_form()
    else:
        show_saved_screen()


if __name__ == "__main__":
    main()
