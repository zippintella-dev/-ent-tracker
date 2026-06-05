import base64
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_geolocation import streamlit_geolocation

IST = ZoneInfo("Asia/Kolkata")

from auth import get_credentials
from storage import upload_image
from sheets import append_trip, update_trip_end, get_daily_roster
from db import get_drivers, get_clients, get_vehicles
from alert_monitor import _compute_shift_expected_time, calculate_delay
from supabase_client import save_trip_to_supabase, update_trip_end_in_supabase, get_incomplete_trip


@st.cache_data(ttl=300, show_spinner=False)
def _cached_today_roster(_creds, date_str: str) -> list:
    return get_daily_roster(_creds, date_str)


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
    st.session_state.setdefault("location_start", None)
    st.session_state.setdefault("location_end", None)


def maps_link(loc) -> str:
    if not loc or loc.get("latitude") is None:
        return "Not available"
    return f"https://maps.google.com/?q={loc['latitude']},{loc['longitude']}"


def trip_id(emp_id: str) -> str:
    return f"{emp_id}_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}"


def _inject_camera_capture():
    """
    After file inputs render, set capture="environment" so mobile browsers
    open the rear camera directly instead of showing the gallery picker.
    Uses window.parent.document because Streamlit components run in iframes.
    """
    components.html("""
        <script>
        (function () {
            function applyCapture() {
                try {
                    window.parent.document
                        .querySelectorAll('input[type="file"]')
                        .forEach(function (el) {
                            el.setAttribute("capture", "environment");
                            el.setAttribute("accept", "image/*");
                        });
                } catch (e) {}
            }
            applyCapture();
            try {
                new MutationObserver(applyCapture).observe(
                    window.parent.document.body,
                    { childList: true, subtree: true }
                );
            } catch (e) {}
        })();
        </script>
    """, height=0)


def camera_block(label: str, key: str):
    return st.file_uploader(
        label,
        type=["jpg", "jpeg", "png"],
        key=key,
    )




def show_start_form():
    show_header()
    st.subheader("Start Trip")

    drivers = get_drivers()
    driver_name = st.selectbox("Driver Name", list(drivers.keys()))
    emp_id = drivers[driver_name]
    st.caption(f"Employee ID: **{emp_id}**  |  Date: **{datetime.now(IST).strftime('%d %b %Y')}**")

    today = datetime.now(IST).strftime("%Y-%m-%d")
    incomplete = get_incomplete_trip(emp_id, today)
    if incomplete:
        st.warning(
            f"⚠️ You have an incomplete trip started at **{incomplete['start_time']}**. "
            "Resume it to submit end details."
        )
        if st.button("▶ Resume Trip", use_container_width=True, type="primary"):
            st.session_state["trip"] = {
                "trip_id":             incomplete["trip_id"],
                "driver_name":         incomplete["driver_name"],
                "emp_id":              incomplete["employee_id"],
                "client":              incomplete["client"],
                "vehicle_number":      incomplete["vehicle_number"],
                "date":                incomplete["trip_date"],
                "start_time":          incomplete["start_time"],
                "start_km":            incomplete.get("start_odometer") or 0,
                "start_location":      incomplete.get("start_location", ""),
                "expected_start_time": incomplete.get("expected_start_time", ""),
                "delay_minutes":       incomplete.get("delay_minutes", 0),
                "status":              incomplete.get("status", ""),
            }
            st.session_state["phase"] = "end"
            st.rerun()
        st.divider()

    clients = get_clients()
    vehicles = get_vehicles()
    if not clients or not vehicles:
        st.warning("No clients or vehicles configured yet. Ask your admin to add them.")
        return
    client = st.selectbox("Client", clients)
    vehicle_number = st.selectbox("Vehicle Number", vehicles)

    st.divider()
    start_km = st.number_input("Start Odometer (km)", min_value=0, step=1, format="%d")

    loc = streamlit_geolocation()
    if loc and loc.get("latitude") is not None:
        st.session_state["location_start"] = loc
    if st.session_state.get("location_start"):
        st.caption("📍 Location captured")
    else:
        st.caption("📍 Press the button above to capture your location")

    st.divider()
    st.subheader("📸 Start Photos")
    _inject_camera_capture()
    left = camera_block("Left Side of Vehicle", "start_left")
    right = camera_block("Right Side of Vehicle", "start_right")
    odo = camera_block("Odometer", "start_odo")

    st.divider()
    if st.button("▶  Start Trip", use_container_width=True, type="primary"):
        missing = [n for n, f in [("Left side", left), ("Right side", right), ("Odometer", odo)] if not f]
        if missing:
            st.warning(f"Please capture: {', '.join(missing)}")
        elif not st.session_state.get("location_start"):
            st.warning("Please capture your location first.")
        else:
            try:
                with st.spinner("Starting trip..."):
                    creds = get_credentials()
                    today = datetime.now(IST).strftime("%Y-%m-%d")
                    start_time = datetime.now(IST).strftime("%H:%M:%S")
                    tid = trip_id(emp_id)

                    roster_rows = _cached_today_roster(creds, today)
                    expected_start = _compute_shift_expected_time(roster_rows, emp_id, today, start_time)
                    delay_minutes = calculate_delay(start_time, expected_start)
                    status = "On Time" if delay_minutes == 0 else "Delayed"

                    start_left_url = upload_image(left.getvalue(), f"{tid}_start_left.jpg")
                    start_right_url = upload_image(right.getvalue(), f"{tid}_start_right.jpg")
                    start_odo_url = upload_image(odo.getvalue(), f"{tid}_start_odo.jpg")

                    start_location = maps_link(st.session_state.get("location_start"))

                    append_trip(creds, {
                        "Trip ID": tid,
                        "Driver Name": driver_name,
                        "Employee ID": emp_id,
                        "Client": client,
                        "Vehicle Number": vehicle_number,
                        "Date": today,
                        "Start Time": start_time,
                        "End Time": "",
                        "Expected Start Time": expected_start,
                        "Delay Minutes": delay_minutes,
                        "Status": status,
                        "Start Odometer (km)": start_km,
                        "End Odometer (km)": "",
                        "Distance (km)": "",
                        "Start Location": start_location,
                        "End Location": "",
                        "Start - Left Photo": start_left_url,
                        "Start - Right Photo": start_right_url,
                        "Start - Odometer Photo": start_odo_url,
                        "End - Left Photo": "",
                        "End - Right Photo": "",
                        "End - Odometer Photo": "",
                        "Submitted At": "",
                    })

                    save_trip_to_supabase({
                        "trip_id":              tid,
                        "driver_name":          driver_name,
                        "employee_id":          emp_id,
                        "client":               client,
                        "vehicle_number":       vehicle_number,
                        "trip_date":            today,
                        "start_time":           start_time,
                        "expected_start_time":  expected_start,
                        "delay_minutes":        delay_minutes,
                        "status":               status,
                        "start_odometer":       start_km,
                        "start_location":       start_location,
                        "start_left_photo":     start_left_url,
                        "start_right_photo":    start_right_url,
                        "start_odometer_photo": start_odo_url,
                    })
            except Exception as e:
                st.error(f"Failed to start trip: {e}")
                return

            st.session_state["trip"] = {
                "trip_id": tid,
                "driver_name": driver_name,
                "emp_id": emp_id,
                "client": client,
                "vehicle_number": vehicle_number,
                "date": today,
                "start_time": start_time,
                "start_km": start_km,
                "start_location": start_location,
                "expected_start_time": expected_start,
                "delay_minutes": delay_minutes,
                "status": status,
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

    st.subheader("End Trip")
    end_km = st.number_input("End Odometer (km)", min_value=0, step=1, format="%d")

    loc = streamlit_geolocation()
    if loc and loc.get("latitude") is not None:
        st.session_state["location_end"] = loc
    if st.session_state.get("location_end"):
        st.caption("📍 Location captured")
    else:
        st.caption("📍 Press the button above to capture your location")

    st.divider()
    st.subheader("📸 End Photos")
    _inject_camera_capture()
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
        st.session_state["location_end"] = None
        st.rerun()

    if submit:
        missing = [n for n, f in [("Left side", left), ("Right side", right), ("Odometer", odo)] if not f]
        if missing:
            st.warning(f"Please capture: {', '.join(missing)}")
            return
        if not st.session_state.get("location_end"):
            st.warning("Please capture your location first.")
            return
        if end_km <= trip["start_km"]:
            st.warning("End odometer must be greater than start odometer.")
            return

        assert left and right and odo  # guaranteed by missing check above

        try:
            with st.spinner("Uploading photos and saving trip..."):
                creds = get_credentials()
                end_time = datetime.now(IST).strftime("%H:%M:%S")
                distance = end_km - trip["start_km"]

                def upload(data, name):
                    return upload_image(data, f"{trip['trip_id']}_{name}.jpg")

                end_location = maps_link(st.session_state.get("location_end"))
                end_left_url = upload(left.getvalue(), "end_left")
                end_right_url = upload(right.getvalue(), "end_right")
                end_odo_url = upload(odo.getvalue(), "end_odo")
                submitted_at = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

                update_trip_end(creds, trip["trip_id"], {
                    "End Time": end_time,
                    "End Odometer (km)": end_km,
                    "Distance (km)": distance,
                    "End Location": end_location,
                    "End - Left Photo": end_left_url,
                    "End - Right Photo": end_right_url,
                    "End - Odometer Photo": end_odo_url,
                    "Submitted At": submitted_at,
                })

                update_trip_end_in_supabase(trip["trip_id"], {
                    "end_time":           end_time,
                    "end_odometer":       end_km,
                    "distance_km":        distance,
                    "end_location":       end_location,
                    "end_left_photo":     end_left_url,
                    "end_right_photo":    end_right_url,
                    "end_odometer_photo": end_odo_url,
                    "submitted_at":       submitted_at,
                })
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
        st.session_state["location_start"] = None
        st.session_state["location_end"] = None
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
