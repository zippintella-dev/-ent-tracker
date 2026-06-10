from db import _get_client


def get_supabase_client():
    return _get_client()


def get_incomplete_trip(emp_id: str) -> dict | None:
    """
    Return the most recent incomplete trip for a driver, regardless of date.
    No date filter — night-shift drivers cross midnight and their trip_date
    would not match today's date after 00:00.
    """
    try:
        result = (
            get_supabase_client()
            .table("trip_logs")
            .select("*")
            .eq("employee_id", emp_id)
            .is_("end_time", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[Supabase] get_incomplete_trip failed: {e}")
        return None


def has_completed_trip_today(emp_id: str, trip_date: str) -> bool:
    """Return True if the driver has at least one completed trip today."""
    try:
        result = (
            get_supabase_client()
            .table("trip_logs")
            .select("trip_id")
            .eq("employee_id", emp_id)
            .eq("trip_date", trip_date)
            .not_.is_("end_time", "null")
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception as e:
        print(f"[Supabase] has_completed_trip_today failed: {e}")
        return False  # fail-safe: treat as first trip so side photos are shown


def get_last_completed_trip_time(emp_id: str):
    """Return IST datetime of driver's most recent completed trip end, or None."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        result = (
            get_supabase_client()
            .table("trip_logs")
            .select("submitted_at")
            .eq("employee_id", emp_id)
            .not_.is_("end_time", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            raw = result.data[0].get("submitted_at", "")
            if raw:
                return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return None
    except Exception as e:
        print(f"[Supabase] get_last_completed_trip_time failed: {e}")
        return None


def save_trip_to_supabase(trip_data: dict):
    """
    Insert trip-start record into trip_logs.
    Non-blocking — a failure here never stops the trip flow.
    End-of-trip fields default to NULL and are filled by update_trip_end_in_supabase().
    """
    try:
        get_supabase_client().table("trip_logs").insert({
            "trip_id":              trip_data["trip_id"],
            "driver_name":          trip_data["driver_name"],
            "employee_id":          trip_data["employee_id"],
            "client":               trip_data["client"],
            "vehicle_number":       trip_data["vehicle_number"],
            "trip_date":            trip_data["trip_date"],
            "start_time":           trip_data["start_time"],
            "expected_start_time":  trip_data.get("expected_start_time", ""),
            "delay_minutes":        trip_data.get("delay_minutes", 0),
            "status":               trip_data.get("status", ""),
            "start_odometer":       trip_data.get("start_odometer"),
            "start_location":       trip_data.get("start_location", ""),
            "start_left_photo":     trip_data.get("start_left_photo", ""),
            "start_right_photo":    trip_data.get("start_right_photo", ""),
            "start_odometer_photo": trip_data.get("start_odometer_photo", ""),
        }).execute()
    except Exception as e:
        print(f"[Supabase] save_trip_to_supabase failed: {e}")


def update_trip_end_in_supabase(trip_id: str, end_data: dict):
    """
    Update the trip_logs row with end-of-trip data.
    Non-blocking — a failure here never stops the submit flow.
    """
    try:
        payload = {
            "end_time":           end_data.get("end_time", ""),
            "end_odometer":       end_data.get("end_odometer"),
            "distance_km":        end_data.get("distance_km"),
            "end_location":       end_data.get("end_location", ""),
            "end_left_photo":     end_data.get("end_left_photo", ""),
            "end_right_photo":    end_data.get("end_right_photo", ""),
            "end_odometer_photo": end_data.get("end_odometer_photo", ""),
            "submitted_at":       end_data.get("submitted_at", ""),
        }
        if end_data.get("revenue") is not None:
            payload["revenue"] = end_data["revenue"]
        get_supabase_client().table("trip_logs").update(payload).eq("trip_id", trip_id).execute()
    except Exception as e:
        print(f"[Supabase] update_trip_end_in_supabase failed: {e}")
