# Tiny Kingdom MCP

A playful MCP server that powers a tiny, evolving kingdom. World state lives in Supabase; OpenAI transforms it based on intents. Built for text-first assistants — tools return short, iMessage‑ready summaries and optional media URLs.

---

## Features
- Persistent world in Supabase (`public.kingdom`, `id = "single_user"`)
- Short, vivid narration (1–2 sentences, tasteful emojis)
- Convenience tools (adventures, festivals, day advance, daily ticks)
- Live context (weather, news) + media search (GIF/image URL)
- Built-in playbook + system prompt tools for your agent
- Admin/cheat pathway (optional)

---

## Quickstart

### 1) Requirements
- Python 3.10+
- Supabase project

### 2) Setup
```bash
git clone <your-repo-url>
cd tiny-kingdom-poke-mcp
python -m venv .venv && source .venv/bin/activate  # or conda
pip install -r requirements.txt
```

Create `.env`:
```env
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
GIPHY_API_KEY=
PORT=8000
```

### 3) Run
```bash
python src/server.py
```
Open MCP Inspector and connect with Streamable HTTP to `http://localhost:8000/mcp`.

---

## Supabase schema
```sql
create table if not exists public.kingdom (
  id text primary key,
  world_state jsonb not null,
  last_updated timestamptz not null default now()
);
insert into public.kingdom (id, world_state)
values ('single_user', '{}'::jsonb)
on conflict (id) do nothing;
```

---

## Tools (high level)

Core:
- `create_kingdom(kingdom_name, theme?)` → `{ ok, summary, backstory, starting_point, last_updated, playbook, system_prompt }`
- `kingdom_action(action, params?)` → `{ ok, summary, last_updated }`
- `kingdom_query(question)` → `{ ok, summary, last_updated }`
- `get_world_state()` → `{ ok, world_state, last_updated }`
- `apply_cheat(name, params?)` → `{ ok, summary, last_updated }`

Wrappers:
- `send_hero_on_adventure(hero_name?)`
- `host_festival(scale?)`
- `advance_day()`
- `daily_tick()`
- `introduce_character(name, role)`
- `narrate(style?)`
- `narrate_with_media(style?, query?)`
- `update_weather_context(city)`
- `set_realm_location(reference_city?, lat?, lon?, climate_theme?)`
- `update_weather_context_from_location()`
- `update_news_context()`
- `find_media_url(query)` → use single words or two-word phrases
- `get_playbook()` / `get_system_prompt()`

---

## Typical flows

Seed + narrate:
```json
{ "kingdom_name": "Verdant Vale", "theme": "cozy fantasy" }
```
```json
{}
```

Action + status:
```json
{ "hero_name": "Glimmer the Brave" }
```
```json
{}
```

Live context + media:
```json
{ "reference_city": "Budapest" }
```
```json
{}
```
```json
{ "style": "snappy", "query": "dragon" }
```

---

## How it works
1) Load `world_state` from Supabase (row `single_user`).
2) Send `{ intent, current_world_state }` to OpenAI in JSON-mode.
3) Receive `{ updated_world_state, summary, metadata }`, persist, return summary (and media URL if found).

Compaction:
- Trim `events_log` when too long; count in `events_log_compacted`
- Clamp long context strings
- Enforce a max JSON size with aggressive trimming if needed

---

## Troubleshooting
- Inspector connection: use Streamable HTTP to `http://localhost:8000/mcp`.
- Keys: `.env` should include OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY; server logs print non‑secret checks.
- Supabase table: ensure `public.kingdom` exists.
- Media: use simple queries; set `GIPHY_API_KEY` for better GIFs.
