import json
from typing import Any, Dict, Tuple

from openai import OpenAI
from config import OPENAI_MODEL

_openai_client: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client


def _normalize_summary(text: str, max_len: int = 220) -> str:
    # collapse whitespace and remove list markers/headings
    if not isinstance(text, str):
        return ""
    t = text.replace("\n", " ").replace("\r", " ")
    # strip common bullet symbols
    for b in ["•", "- ", "– ", "— "]:
        t = t.replace(b, "")
    # collapse multiple spaces
    while "  " in t:
        t = t.replace("  ", " ")
    t = t.strip()
    # hard cap length
    if len(t) > max_len:
        t = t[:max_len - 1].rstrip() + "…"
    return t


def llm_transform_world_state(intent: Dict[str, Any], current_world_state: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    client = _get_openai()

    system = (
        # role & output contract
        "You are the simulation engine and narrator of Tiny Kingdom. "
        "Output STRICT JSON with keys: updated_world_state (object), summary (string), metadata (object). "
        "Do not include code fences or extra text outside JSON. "

        # persona
        "Persona: Quill, the kingdom’s mischievous court chronicler — warm, witty, and brave-hearted. "
        "Quill delights in small details (sounds, smells, local quirks), cracks gentle jokes, and cheers on heroes. "
        "Voice: whimsical but clear, never rambling; avoids modern slang unless playful. "

        # narrative style
        "Narration must be action-driven, vivid, and fun; present tense; at most 2 sentences and ~180 characters (trim if longer). "
        "Include 1–2 fitting emojis in the summary (at least 1 unless the tone is solemn). "
        "Never use headings. Never use bullet points or multi-line lists. Prefer concrete actions and consequences. Do not include links or images. "

        # state mutation rules
        "Modify the world_state ONLY as required by the intent; for queries, changes should be minimal (e.g., append a log). "
        "Maintain continuity: keep existing names consistent; never wipe arrays; do not explode state size. "
        "When you change resources or characters, keep values reasonable (e.g., morale 0–100). "
        "Append an events_log entry for notable happenings with: {type, description, at (ISO8601)}. "

        # story shaping
        "Arcs: Favor multi-day arcs (quests, festivals, construction) with short milestone updates. "
        "Choices: Occasionally offer a single lightweight choice (A/B or yes/no) that can be actioned next. Keep it short. "
        "Pacing: Mostly slice-of-life with occasional high-stakes beats; escalate stakes sparingly. "

        # call-to-action options
        "At the very end of the summary, append: ' Options: (1) <short>; (2) <short>; (3) <short>' using three brief, 2–4 word next-actions relevant to the state. "

        # admin/Cheat commands
        "If intent.type is 'cheat', apply the requested changes VERBATIM, even if they exceed normal bounds (e.g., infinite health, morale 1000). "
        "Create missing fields as needed; keep structure coherent. Always append an events_log entry with type 'cheat'. "
        "Still keep the summary short (1–2 sentences) and include 1–2 emojis. "

        # init template
        "If intent.type is 'init', create a fresh world with at least: "
        "kingdom_name (string), day (number starting at 1), resources {gold, food, morale}, heroes[] (name, level, status), "
        "villagers[] (name, role), events_log[] (can start empty), context {} (weather/news optional), backstory (string), starting_point (string)."
    )

    user_payload = {
        "intent": intent,
        "current_world_state": current_world_state,
        "requirements": {
            "response_shape": {
                "updated_world_state": "object",
                "summary": "string",
                "metadata": {"changed": "boolean"}
            }
        }
    }

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ],
        temperature=0.7,
    )

    content = completion.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except Exception:
        return current_world_state, "An update occurred, but I couldn't parse details."

    updated_world_state = parsed.get("updated_world_state")
    summary = parsed.get("summary")

    if not isinstance(updated_world_state, dict):
        updated_world_state = current_world_state
        if not isinstance(summary, str) or not summary:
            summary = "No changes were applied."

    if not isinstance(summary, str) or not summary:
        summary = "The kingdom stirs, but nothing noteworthy happened."

    summary = _normalize_summary(summary)

    return updated_world_state, summary


