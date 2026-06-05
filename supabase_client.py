from db import _get_client


def get_supabase_client():
    return _get_client()


def get_incomplete_trip(emp_id: str, trip_date: str) -> dict | None:
    """Return the most recent incomplete trip for a driver today, or None."""
    try:
        result = (
            get_supabase_client()
            .table("trip_logs")
            .select("*")
            .eq("employee_id", emp_id)
            .eq("trip_date", trip_date)
            .is_("end_time", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[Supabase] get_incomplete_trip failed: {e}")
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
        get_supabase_client().table("trip_logs").update({
            "end_time":           end_data.get("end_time", ""),
            "end_odometer":       end_data.get("end_odometer"),
            "distance_km":        end_data.get("distance_km"),
            "end_location":       end_data.get("end_location", ""),
            "end_left_photo":     end_data.get("end_left_photo", ""),
            "end_right_photo":    end_data.get("end_right_photo", ""),
            "end_odometer_photo": end_data.get("end_odometer_photo", ""),
            "submitted_at":       end_data.get("submitted_at", ""),
        }).eq("trip_id", trip_id).execute()
    except Exception as e:
        print(f"[Supabase] update_trip_end_in_supabase failed: {e}")
