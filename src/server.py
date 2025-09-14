import os
from typing import Any, Dict, Optional
from fastmcp import FastMCP
from db import load_world_state, save_world_state
from llm import llm_transform_world_state as llm_transform
from integrations import (
    fetch_weather_summary,
    fetch_trending_news_summary,
    fetch_media_url,
    fetch_weather_by_coords,
)

mcp = FastMCP("Tiny Kingdom")


# internal stuff
def _perform_kingdom_action(action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    world_state, _ = load_world_state()
    intent = {"type": "action", "name": action, "params": params or {}}
    updated_state, summary = llm_transform(intent, world_state)
    last_updated = save_world_state(updated_state)
    return {"ok": True, "summary": summary, "last_updated": last_updated}


def _perform_kingdom_query(question: str) -> Dict[str, Any]:
    world_state, _ = load_world_state()
    intent = {"type": "query", "question": question}
    updated_state, summary = llm_transform(intent, world_state)
    last_updated = save_world_state(updated_state)
    return {"ok": True, "summary": summary, "last_updated": last_updated}


def _build_playbook_dict() -> Dict[str, Any]:
    return {
        "objective": "Delight the user with a lively, evolving micro-kingdom: short, vivid summaries + sensible state changes.",
        "narrative_style": {
            "tense": "present",
            "length": "one short paragraph",
            "emojis": "use tastefully (0–2)",
            "tone": "fun, action-driven, concrete consequences"
        },
        "pacing": "Poke can call advance_day when it makes story sense (e.g., once per real day, after a set of actions, or when user asks). Poke may also occasionally trigger random events to keep things lively (e.g., sudden attacks, traveling merchants). Avoid spamming—at most a couple per day.",
        "state_rules": [
            "Change only what the intent requires; for queries, prefer minimal changes (append a log).",
            "Keep resources in sane ranges (morale 0–100).",
            "Maintain continuity: consistent names; don't wipe arrays; avoid state bloat.",
            "Append events_log entries for notable happenings: {type, description, at}."
        ],
        "common_tools": [
            {
                "name": "apply_cheat",
                "purpose": "Admin/cheat: apply direct changes (e.g., infinite health).",
                "args": {"name": "string", "params": "object?"},
                "example": {"name": "set_hero_health", "params": {"hero_name": "Glimmer the Brave", "health": "infinite"}}
            },
            {
                "name": "advance_day",
                "purpose": "Advance simulation by one day and summarize changes.",
                "args": {},
                "example": {}
            },
            {
                "name": "create_kingdom",
                "purpose": "Initialize/reset world with backstory and starting point.",
                "args": {"kingdom_name": "string", "theme": "string?"},
                "example": {"kingdom_name": "Verdant Vale", "theme": "cozy fantasy"}
            },
            {
                "name": "send_hero_on_adventure",
                "purpose": "Trigger a bite-sized quest and update resources/hero.",
                "args": {"hero_name": "string?"},
                "example": {"hero_name": "Glimmer the Brave"}
            },
            {
                "name": "host_festival",
                "purpose": "Boost morale (costs some food), log an event.",
                "args": {"scale": "small|medium|large?"},
                "example": {"scale": "small"}
            },
            {
                "name": "introduce_character",
                "purpose": "Add a new named villager with a role.",
                "args": {"name": "string", "role": "string"},
                "example": {"name": "Nix the Tinkerer", "role": "inventor"}
            },
            {
                "name": "update_weather_context",
                "purpose": "Fetch real weather for a reference city and store in context.weather.",
                "args": {"city": "string"},
                "example": {"city": "Budapest"}
            },
            {
                "name": "update_news_context",
                "purpose": "Fetch a short trending blurb and store in context.news.",
                "args": {},
                "example": {}
            },
            {
                "name": "narrate",
                "purpose": "Ask for today’s update; returns a short story paragraph.",
                "args": {"style": "string?"},
                "example": {"style": "whimsical and fast-paced"}
            },
            {
                "name": "find_media_url",
                "purpose": "Return a GIF/image URL. Use single words or two-word phrases for the query.",
                "args": {"query": "string"},
                "example": {"query": "dragon"}
            },
            {
                "name": "kingdom_action",
                "purpose": "Low-level action interface if a wrapper doesn't exist.",
                "args": {"action": "string", "params": "object?"},
                "example": {"action": "collect_taxes"},
                "random_event_examples": [
                    {"action": "sudden_attack", "params": {"threat": "bandits"}},
                    {"action": "traveling_merchant", "params": {"goods": "rare trinkets"}},
                    {"action": "mysterious_stranger", "params": {"mood": "ominous"}}
                ]
            },
            {
                "name": "kingdom_query",
                "purpose": "Ask questions or request summaries with minimal state change.",
                "args": {"question": "string"},
                "example": {"question": "Summarize the day in one paragraph with 2 emojis."}
            }
        ],
        "session_bootstrap": [
            "Call get_world_state; if empty, call create_kingdom.",
            "Optionally call update_weather_context and update_news_context.",
            "Call narrate for the daily message, then act based on user requests."
        ],
        "response_contract": {
            "summary": "Always return a concise, iMessage-friendly paragraph."
        }
    }


def _build_system_prompt_str() -> str:
    return (
        "REMEMEBER: you can take the summary and make it into separate short cohesive texts like in the same length as you usually send"
        "You are Poke, a messaging assistant running a playful Tiny Kingdom simulation via MCP tools. "
        "Always be concise, friendly, and action-driven.\n\n"
        "Persona: Quill, the kingdom’s mischievous court chronicler — warm, witty, and brave-hearted. "
        "Delight in small sensory details, crack gentle jokes, and cheer on heroes.\n\n"
        "Output style: 1–2 short sentences (≤150 chars) per reply (message bubble), can send multiple messages, present tense, include 1–2 fitting emojis. "
        "Avoid lists, code blocks, or links (except media URLs when explicitly requested).\n\n"
        "Continuity & state: Maintain consistent names; only change world_state when a tool call requires it; for summaries, prefer minimal changes (append events_log). "
        "Keep resources sane unless a cheat is requested.\n\n"
        "Pacing: You may call advance_day when it fits the story (e.g., once per real day, after actions, or when asked). "
        "Occasionally inject random events to keep things lively (e.g., sudden attacks, traveling merchants), but do not spam.\n\n"
        "Common actions (use wrappers when possible): create_kingdom, send_hero_on_adventure, host_festival, introduce_character, narrate, advance_day. "
        "Context: update_weather_context(city), update_news_context(). "
        "Media: when asked for a visual, call find_media_url(query) and include the returned URL. "
        "Cheats: if the user asks, use apply_cheat(name, params) to apply changes verbatim and log an events_log entry of type 'cheat'.\n\n"
        "Contract: Keep replies short and story-like with concrete consequences; if a tool returns a summary."
    )



# MCP tools for Supabase + LLM loop

@mcp.tool(description="Perform an action in the kingdom via LLM: updates state and returns a summary")
def kingdom_action(action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print(f"[MCP] tool=kingdom_action action={action} params={params or {}}")
    return _perform_kingdom_action(action, params)


@mcp.tool(description="Ask about the kingdom via LLM: may update state minimally, returns a summary")
def kingdom_query(question: str) -> Dict[str, Any]:
    print(f"[MCP] tool=kingdom_query question={question}")
    return _perform_kingdom_query(question)


@mcp.tool(description="Get the current kingdom world_state (debug/admin)")
def get_world_state() -> Dict[str, Any]:
    print("[MCP] tool=get_world_state")
    world_state, last_updated = load_world_state()
    return {"ok": True, "world_state": world_state, "last_updated": last_updated}


@mcp.tool(description="Create or reset the kingdom with a given name; returns backstory and starting point")
def create_kingdom(kingdom_name: str, theme: Optional[str] = None) -> Dict[str, Any]:
    """Initialize a new kingdom via the LLM and persist it. Overwrites existing state."""
    print(f"[MCP] tool=create_kingdom kingdom_name={kingdom_name} theme={theme}")
    # for init we pass an empty current state to fully rebuild
    intent: Dict[str, Any] = {"type": "init", "kingdom_name": kingdom_name}
    if theme:
        intent["theme"] = theme

    updated_state, summary = llm_transform(intent, {})
    # ensure the intended name is recorded
    if isinstance(updated_state, dict):
        updated_state.setdefault("kingdom_name", kingdom_name)

    last_updated = save_world_state(updated_state if isinstance(updated_state, dict) else {})

    backstory = ""
    starting_point = ""
    if isinstance(updated_state, dict):
        backstory = str(updated_state.get("backstory") or "")
        starting_point = str(updated_state.get("starting_point") or "")

    # return playbook and system prompt so the agent can bootstrap itself
    result: Dict[str, Any] = {
        "ok": True,
        "summary": summary,
        "backstory": backstory,
        "starting_point": starting_point,
        "last_updated": last_updated,
        "playbook": _build_playbook_dict(),
        "system_prompt": _build_system_prompt_str(),
    }
    return result


# convenience wrapper tools for common actions/narration

@mcp.tool(description="Send a hero on an adventure with optional hero_name param")
def send_hero_on_adventure(hero_name: Optional[str] = None) -> Dict[str, Any]:
    print(f"[MCP] tool=send_hero_on_adventure hero_name={hero_name}")
    params: Dict[str, Any] = {}
    if hero_name:
        params["hero_name"] = hero_name
    return _perform_kingdom_action("send_hero_on_adventure", params)


@mcp.tool(description="Host a festival; params.scale can be 'small'|'medium'|'large'")
def host_festival(scale: Optional[str] = None) -> Dict[str, Any]:
    print(f"[MCP] tool=host_festival scale={scale}")
    params: Dict[str, Any] = {}
    if scale:
        params["scale"] = scale
    return _perform_kingdom_action("host_festival", params)


@mcp.tool(description="Introduce a new character to the kingdom (name and role)")
def introduce_character(name: str, role: str) -> Dict[str, Any]:
    print(f"[MCP] tool=introduce_character name={name} role={role}")
    return _perform_kingdom_action("introduce_character", {"name": name, "role": role})


@mcp.tool(description="Ask the narrator for today’s update in one short paragraph")
def narrate(style: Optional[str] = None) -> Dict[str, Any]:
    print(f"[MCP] tool=narrate style={style}")
    question = (
        "Give me today’s update in 1–2 short sentences (<=180 chars) with 1–2 fitting emojis. "
        "No headings, no bullet lists. End with: Options: (1) <short>; (2) <short>; (3) <short>."
    )
    if style:
        question = f"{question} Style: {style}."
    return _perform_kingdom_query(question)


@mcp.tool(description="Narrate and include a fitting media URL if available (use single words or two-word phrases for media search)")
async def narrate_with_media(style: Optional[str] = None, query: Optional[str] = None) -> Dict[str, Any]:
    print(f"[MCP] tool=narrate_with_media style={style} query={query}")
    # yse internal helper to avoid calling a decorated tool from another tool
    question = (
        "Give me today’s update in 1–2 short sentences (<=180 chars) with 1–2 fitting emojis. "
        "No headings, no bullet lists. End with: Options: (1) <short>; (2) <short>; (3) <short>."
    )
    if style:
        question = f"{question} Style: {style}."
    base = _perform_kingdom_query(question)
    # try a simple media query: use provided query or fallback to kingdom_name or generic
    world_state, _ = load_world_state()
    q = query or (isinstance(world_state, dict) and world_state.get("kingdom_name")) or "fantasy"
    url = await fetch_media_url(str(q))
    if url:
        base["media_url"] = url
    return base


@mcp.tool(description="Advance the kingdom by one day and return a summary")
def advance_day() -> Dict[str, Any]:
    print("[MCP] tool=advance_day")
    return _perform_kingdom_action("advance_day", {})


@mcp.tool(description="Fetch live weather for a real, existing city (choose one which is not fictional, but resembles the kingdom) and save to context.weather")
async def update_weather_context(city: str) -> Dict[str, Any]:
    print(f"[MCP] tool=update_weather_context city={city}")
    world_state, _ = load_world_state()
    summary = await fetch_weather_summary(city)
    if not summary:
        return {"ok": False, "message": "Could not fetch weather"}
    ws = dict(world_state)
    ctx = dict(ws.get("context") or {})
    ctx["weather"] = summary
    ws["context"] = ctx
    last_updated = save_world_state(ws)
    return {"ok": True, "weather": summary, "last_updated": last_updated}


@mcp.tool(description="Set the realm location reference (city or coordinates, or a climate theme)")
def set_realm_location(reference_city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, climate_theme: Optional[str] = None) -> Dict[str, Any]:
    print(f"[MCP] tool=set_realm_location city={reference_city} lat={lat} lon={lon} theme={climate_theme}")
    world_state, _ = load_world_state()
    ws = dict(world_state)
    ctx = dict(ws.get("context") or {})
    location: Dict[str, Any] = {}
    if reference_city:
        location["city"] = reference_city
    if lat is not None and lon is not None:
        location["lat"] = lat
        location["lon"] = lon
    if climate_theme:
        location["climate_theme"] = climate_theme
    ctx["location"] = location
    ws["context"] = ctx
    last_updated = save_world_state(ws)
    return {"ok": True, "location": location, "last_updated": last_updated}


@mcp.tool(description="Fetch weather based on stored realm location and save to context.weather")
async def update_weather_context_from_location() -> Dict[str, Any]:
    print("[MCP] tool=update_weather_context_from_location")
    world_state, _ = load_world_state()
    ctx = dict((world_state or {}).get("context") or {})
    loc = dict(ctx.get("location") or {})
    summary: Optional[str] = None
    if "lat" in loc and "lon" in loc:
        summary = await fetch_weather_by_coords(float(loc["lat"]), float(loc["lon"]))
    elif "city" in loc:
        summary = await fetch_weather_summary(str(loc["city"]))
    else:
        # Fall back to climate theme if present
        theme = loc.get("climate_theme")
        if isinstance(theme, str) and theme:
            summary = f"themed weather: {theme}"
    if not summary:
        return {"ok": False, "message": "No stored location info"}
    ctx["weather"] = summary
    ws = dict(world_state)
    ws["context"] = ctx
    last_updated = save_world_state(ws)
    return {"ok": True, "weather": summary, "last_updated": last_updated}


@mcp.tool(description="Apply a tiny background tick (resource drift) with minimal narrative change")
def daily_tick() -> Dict[str, Any]:
    print("[MCP] tool=daily_tick")
    # nudge via action so LLM applies minimal changes per rules
    return _perform_kingdom_action("daily_tick", {})


@mcp.tool(description="Fetch a short trending news blurb and save to context.news")
async def update_news_context() -> Dict[str, Any]:
    print("[MCP] tool=update_news_context")
    world_state, _ = load_world_state()
    blurb = await fetch_trending_news_summary()
    if not blurb:
        return {"ok": False, "message": "Could not fetch news"}
    ws = dict(world_state)
    ctx = dict(ws.get("context") or {})
    ctx["news"] = blurb
    ws["context"] = ctx
    last_updated = save_world_state(ws)
    return {"ok": True, "news": blurb, "last_updated": last_updated}


@mcp.tool(description="Return a concise playbook for how poke should play Tiny Kingdom")
def get_playbook() -> Dict[str, Any]:
    print("[MCP] tool=get_playbook")
    return _build_playbook_dict()


@mcp.tool(description="Find a fitting media URL (gif or image); search with single words or two-word phrases")
async def find_media_url(query: str) -> Dict[str, Any]:
    print(f"[MCP] tool=find_media_url query={query}")
    url = await fetch_media_url(query)
    if not url:
        return {"ok": False, "message": "No media found"}
    return {"ok": True, "url": url}


@mcp.tool(description="Return a single-string system prompt for Poke to run Tiny Kingdom")
def get_system_prompt() -> Dict[str, Any]:
    print("[MCP] tool=get_system_prompt")
    return {"ok": True, "system_prompt": _build_system_prompt_str()}


@mcp.tool(description="Apply a cheat/admin change directly to world_state via LLM (unsafe)")
def apply_cheat(name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print(f"[MCP] tool=apply_cheat name={name} params={params}")
    world_state, _ = load_world_state()
    intent = {"type": "cheat", "name": name, "params": params or {}}
    updated_state, summary = llm_transform(intent, world_state)
    last_updated = save_world_state(updated_state)
    return {"ok": True, "summary": summary, "last_updated": last_updated}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    # startup env diagnostics (non-secret)
    from config import SUPABASE_URL, OPENAI_MODEL, GIPHY_API_KEY
    print(f"Starting Tiny Kingdom MCP server on {host}:{port}")
    print("Env checks:")
    print(f"- SUPABASE_URL set: {bool(SUPABASE_URL)}")
    print(f"- OPENAI_MODEL: {OPENAI_MODEL}")
    print(f"- Using OpenAI directly: True")
    print(f"- GIPHY key set: {bool(GIPHY_API_KEY)}")
    
    mcp.run(
        transport="http",
        host=host,
        port=port
    )
