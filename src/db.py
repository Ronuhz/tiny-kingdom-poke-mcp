from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import json

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

TABLE = "kingdom"
ROW_ID = "single_user"

_supabase_client: Optional[Client] = None


def _get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_client


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


MAX_JSON_BYTES = 200_000  # ~200KB safeguard
MAX_EVENTS = 200
KEEP_EVENTS = 100


def compact_world_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Compact world_state when it grows too large.
    - Trim events_log to the last KEEP_EVENTS if length exceeds MAX_EVENTS.
    - Add events_log_compacted count of removed entries.
    - Clamp overly long context strings.
    - If JSON still exceeds MAX_JSON_BYTES, aggressively cut events to last 25.
    """
    ws = dict(state)
    events = list((ws.get("events_log") or []))
    removed = 0
    if len(events) > MAX_EVENTS:
        removed = len(events) - KEEP_EVENTS
        events = events[-KEEP_EVENTS:]
        ws["events_log"] = events
        prev = int(ws.get("events_log_compacted") or 0)
        ws["events_log_compacted"] = prev + removed

    # clamp context string sizes
    ctx = dict(ws.get("context") or {})
    for key in ["weather", "news"]:
        val = ctx.get(key)
        if isinstance(val, str) and len(val) > 300:
            ctx[key] = val[:300]
    ws["context"] = ctx

    try:
        size = len(json.dumps(ws, ensure_ascii=False))
    except Exception:
        return ws

    if size > MAX_JSON_BYTES:
        # aggressive trim of events
        if events:
            keep = events[-25:]
            extra_removed = len(events) - len(keep)
            ws["events_log"] = keep
            prev = int(ws.get("events_log_compacted") or 0)
            ws["events_log_compacted"] = prev + max(0, extra_removed)

    return ws


def load_world_state() -> Tuple[Dict[str, Any], Optional[str]]:
    sb = _get_supabase()
    res = sb.table(TABLE).select("world_state,last_updated").eq("id", ROW_ID).single().execute()
    data = getattr(res, "data", None) or {}
    world_state = data.get("world_state") if isinstance(data.get("world_state"), dict) else {}
    last_updated = data.get("last_updated")

    if not data:
        now = _utc_now_iso()
        sb.table(TABLE).upsert({
            "id": ROW_ID,
            "world_state": {},
            "last_updated": now,
        }).execute()
        return {}, now

    return world_state, last_updated


def save_world_state(updated_world_state: Dict[str, Any]) -> str:
    sb = _get_supabase()
    now = _utc_now_iso()
    compacted = compact_world_state(updated_world_state)
    sb.table(TABLE).upsert({
        "id": ROW_ID,
        "world_state": compacted,
        "last_updated": now,
    }).execute()
    return now


