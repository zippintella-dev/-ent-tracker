import streamlit as st

DRIVERS = {
    "Ramesh Kumar (EMP001)": "EMP001",
    "Suresh Patel (EMP002)": "EMP002",
    "Mahesh Singh (EMP003)": "EMP003",
    "Dinesh Rao (EMP004)": "EMP004",
}


def driver_selector():
    st.subheader("Driver")
    selected = st.selectbox("Select your name", list(DRIVERS.keys()), label_visibility="collapsed")
    emp_id = DRIVERS[selected]
    st.caption(f"Employee ID: {emp_id}")
    return selected, emp_id


def odometer_inputs():
    st.subheader("Odometer Reading")
    col1, col2 = st.columns(2)
    with col1:
        start_km = st.number_input("Start (km)", min_value=0, step=1, format="%d")
    with col2:
        end_km = st.number_input("End (km)", min_value=0, step=1, format="%d")
    return start_km, end_km


def image_uploads():
    st.subheader("Photos")
    labels = ["Start Odometer", "End Odometer", "Vehicle / Other"]
    files = []
    for label in labels:
        f = st.camera_input(label, key=f"cam_{label}")
        files.append(f)
    return files


def trip_actions():
    st.subheader("Trip")
    col1, col2 = st.columns(2)
    with col1:
        start = st.button("▶  Start Trip", use_container_width=True, type="primary")
    with col2:
        end = st.button("⏹  End Trip", use_container_width=True)
    return start, end


def main():
    st.set_page_config(page_title="Zippi Trip Tracker", page_icon="🚗", layout="centered")
    st.title("🚗 Zippi Trip Tracker")

    driver_name, emp_id = driver_selector()
    st.divider()

    start_km, end_km = odometer_inputs()
    st.divider()

    images = image_uploads()
    st.divider()

    start_clicked, end_clicked = trip_actions()

    if start_clicked:
        if not any(images[:1]):
            st.warning("Please upload the Start Odometer photo before starting.")
        else:
            st.success(f"Trip started for {driver_name} at {start_km} km.")
            st.session_state["trip_started"] = True

    if end_clicked:
        if not st.session_state.get("trip_started"):
            st.error("No active trip found. Press Start Trip first.")
        elif end_km <= start_km:
            st.warning("End km must be greater than Start km.")
        elif not any(images[1:2]):
            st.warning("Please upload the End Odometer photo before ending.")
        else:
            distance = end_km - start_km
            st.success(f"Trip ended. Distance: {distance} km.")
            st.session_state["trip_started"] = False


if __name__ == "__main__":
    main()
