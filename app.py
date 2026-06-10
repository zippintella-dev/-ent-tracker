import base64
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_geolocation import streamlit_geolocation

IST = ZoneInfo("Asia/Kolkata")

from auth import get_credentials
from storage import upload_image
from sheets import append_trip, update_trip_end, get_daily_roster
from db import get_drivers, get_clients, get_vehicles
from alert_monitor import _compute_shift_expected_time, calculate_delay
from supabase_client import (
    save_trip_to_supabase, update_trip_end_in_supabase,
    get_incomplete_trip, has_completed_trip_today,
)
from billing_engine import calculate_revenue


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
    st.session_state.setdefault("confirm_high_distance", False)
    st.session_state.setdefault("start_photos", {})
    st.session_state.setdefault("end_photos", {})


def maps_link(loc) -> str:
    if not loc or loc.get("latitude") is None:
        return "Not available"
    return f"https://maps.google.com/?q={loc['latitude']},{loc['longitude']}"


def trip_id(emp_id: str) -> str:
    return f"{emp_id}_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}"


_REAR_CAM_PATCH = (
    "<img src='x' onerror=\""
    "if(!window._rp){"
    "window._rp=1;"
    "var o=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);"
    "navigator.mediaDevices.getUserMedia=function(c){"
    "if(c&&c.video&&typeof c.video==='object')c.video.facingMode={ideal:'environment'};"
    "return o(c)"
    "};"
    "}this.remove()\" style='display:none'>"
)


def camera_block(label: str, key: str) -> bytes | None:
    st.markdown(_REAR_CAM_PATCH, unsafe_allow_html=True)
    img = st.camera_input(label, key=key)
    return img.read() if img else None


def _next_photo(photos: dict, steps: list) -> tuple | None:
    return next(((k, l) for k, l in steps if not photos.get(k)), None)




def show_start_form():
    show_header()
    st.subheader("Start Trip")

    drivers = get_drivers()
    driver_name = st.selectbox("Driver Name", list(drivers.keys()))
    emp_id = drivers[driver_name]
    st.caption(f"Employee ID: **{emp_id}**  |  Date: **{datetime.now(IST).strftime('%d %b %Y')}**")

    today = datetime.now(IST).strftime("%Y-%m-%d")
    incomplete = get_incomplete_trip(emp_id)
    if incomplete:
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
    is_first_trip = not has_completed_trip_today(emp_id, today)
    st.subheader("📸 Start Photos")

    if is_first_trip:
        photo_steps = [("left", "Left Side of Vehicle"), ("right", "Right Side of Vehicle"), ("odo", "Odometer")]
        st.caption("First trip of your shift — 3 photos, one at a time")
    else:
        photo_steps = [("odo", "Odometer")]
        st.caption("Side photos only required on your first trip of the shift")

    photos = st.session_state["start_photos"]
    for key, label in photo_steps:
        if photos.get(key):
            st.caption(f"✅ {label}")
    pending = _next_photo(photos, photo_steps)
    if pending:
        key, label = pending
        taken = camera_block(label, f"sc_{key}")
        if taken:
            photos[key] = taken
            st.rerun()
    else:
        st.success("All photos captured")

    st.divider()
    if st.button("▶  Start Trip", use_container_width=True, type="primary"):
        photos = st.session_state["start_photos"]
        pending = _next_photo(photos, photo_steps)
        if pending:
            st.warning(f"Please capture the {pending[1]} photo first.")
        elif not st.session_state.get("location_start"):
            st.warning("Please capture your location first.")
        elif start_km == 0:
            st.warning("Please enter your actual odometer reading. It cannot be 0.")
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

                    start_left_url  = upload_image(photos["left"],  f"{tid}_start_left.jpg")  if photos.get("left")  else ""
                    start_right_url = upload_image(photos["right"], f"{tid}_start_right.jpg") if photos.get("right") else ""
                    start_odo_url   = upload_image(photos["odo"],   f"{tid}_start_odo.jpg")

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
            st.session_state["start_photos"] = {}
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
    end_photos = st.session_state["end_photos"]

    if not end_photos.get("odo"):
        taken = camera_block("Odometer", "ec_odo")
        if taken:
            end_photos["odo"] = taken
            st.rerun()
    else:
        st.caption("✅ Odometer")
        last_trip = st.checkbox("This is my last trip of the shift", key="end_last_trip_check")
        if last_trip:
            if not end_photos.get("left"):
                taken = camera_block("Left Side of Vehicle", "ec_left")
                if taken:
                    end_photos["left"] = taken
                    st.rerun()
            else:
                st.caption("✅ Left Side")
                if not end_photos.get("right"):
                    taken = camera_block("Right Side of Vehicle", "ec_right")
                    if taken:
                        end_photos["right"] = taken
                        st.rerun()
                else:
                    st.caption("✅ Right Side")

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
        st.session_state["confirm_high_distance"] = False
        st.session_state["end_photos"] = {}
        st.rerun()

    if submit:
        end_photos = st.session_state["end_photos"]
        if not end_photos.get("odo"):
            st.warning("Please capture the Odometer photo.")
            return
        if not st.session_state.get("location_end"):
            st.warning("Please capture your location first.")
            return
        if end_km <= trip["start_km"]:
            st.warning("End odometer must be greater than start odometer.")
            return
        projected_distance = end_km - trip["start_km"]
        if projected_distance > 100 and not st.session_state.get("confirm_high_distance"):
            st.warning(
                f"⚠️ Calculated distance is **{projected_distance} km** — this seems unusually high. "
                "Please verify your odometer readings."
            )
            col_a, col_b = st.columns(2)
            if col_a.button("✅ Readings are correct, submit", type="primary"):
                st.session_state["confirm_high_distance"] = True
                st.rerun()
            col_b.button("✏️ Re-enter odometer")
            return

        try:
            with st.spinner("Uploading photos and saving trip..."):
                creds = get_credentials()
                end_time = datetime.now(IST).strftime("%H:%M:%S")
                distance = end_km - trip["start_km"]
                revenue  = calculate_revenue(trip["client"], distance)

                def upload(data, name):
                    return upload_image(data, f"{trip['trip_id']}_{name}.jpg")

                end_location = maps_link(st.session_state.get("location_end"))
                end_photos    = st.session_state["end_photos"]
                end_odo_url   = upload(end_photos["odo"],   "end_odo")
                end_left_url  = upload(end_photos["left"],  "end_left")  if end_photos.get("left")  else ""
                end_right_url = upload(end_photos["right"], "end_right") if end_photos.get("right") else ""
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
                    "revenue":            revenue,
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
        st.session_state["confirm_high_distance"] = False
        st.session_state["end_photos"] = {}
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
        st.session_state["start_photos"] = {}
        st.session_state["end_photos"] = {}
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
