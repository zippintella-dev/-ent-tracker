from supabase_client import get_supabase_client


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_all_billing_rules() -> list[dict]:
    result = (
        get_supabase_client()
        .table("billing_rules")
        .select("*")
        .order("client_name")
        .execute()
    )
    return result.data


def get_active_rules_for_client(client_name: str) -> list[dict]:
    result = (
        get_supabase_client()
        .table("billing_rules")
        .select("*")
        .eq("client_name", client_name)
        .eq("active", True)
        .order("min_km")
        .execute()
    )
    return result.data


def add_billing_rule(rule: dict):
    get_supabase_client().table("billing_rules").insert(rule).execute()


def update_billing_rule(rule_id: int, updates: dict):
    get_supabase_client().table("billing_rules").update(updates).eq("id", rule_id).execute()


# ── Revenue calculation ───────────────────────────────────────────────────────

def calculate_revenue(client_name: str, distance_km: float) -> float | None:
    """
    Returns revenue for a trip, or None if no matching rule exists.

    FLAT  — fixed amount per trip regardless of distance.
    SLAB  — amount for the slab where min_km <= distance_km <= max_km.
    """
    rules = get_active_rules_for_client(client_name)
    if not rules:
        return None

    billing_type = rules[0]["billing_type"]

    if billing_type == "FLAT":
        return float(rules[0]["amount"])

    if billing_type == "SLAB":
        for rule in rules:
            lo = float(rule["min_km"] or 0)
            hi = float(rule["max_km"] or 1e9)
            if lo <= distance_km <= hi:
                return float(rule["amount"])
        return None  # distance falls outside all defined slabs

    return None
