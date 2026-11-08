# Phase 5 — the days

It fills the days of the trip, in three steps, and **stops after each one** for the user's agreement:

1. the **overview**: one line per day;
2. the **proposals**: more things to do than the days can hold, among which the user chooses;
3. the **detail** of each day.

Times and durations in this phase are **indicative**: phase 6 checks opening hours and the times between stops with the map service.

## 0. The map service and its key

Places are looked up with the map service of the trip (`trip.map_provider`): `osm`, `mapbox` or `google`.

- With `osm` nothing is needed.
- With `mapbox` or `google`, run `keys`. When the key is missing, ask for it, in one short message:
  - **Mapbox**: a free account on mapbox.com; on the Tokens page, the *Default public token*, which starts with `pk.`. Never a secret token (`sk.`).
  - **Google**: a project on the Google Cloud console with *Places API (New)* enabled (a credit card is needed to activate it; there is a free monthly quota); then an API key, best **restricted to Places API (New) and Routes API**.
  - Ask the user to paste it in the chat. Save it with `set-key`; never repeat it in your messages and never write it anywhere else (not in the trip file, not in the profile, not in notes).
  - If the user has doubts about pasting the key in the chat, run `keys` and explain how to write it themselves: open the file shown in `file` with a text editor (create it if it does not exist) and write `{"mapbox": "pk...."}` or `{"google": "AIza..."}`; then tell you when it is done, and run `keys` to check.
  - If the user prefers not to give a key now, offer to use OpenStreetMap for this trip: with their yes set `trip.map_provider` to `osm`, write the choice in the log, and go on.
- When `find-place` answers that the key was refused, tell the user plainly (wrong key, or the service not enabled for it) and ask for a new one, or offer OpenStreetMap.

With `osm`, the results come from OpenStreetMap: mention once that the final documents will credit "© OpenStreetMap contributors".

## 1. The overview

Read the trip file: dates, stays (the bases), transports, travellers (pace, interests, mobility), constraints (trip types, what to avoid), the chosen route and its day trips, the open points of phase `days`.

Write one line per day, from the first to the last: the base, a **theme** ("Asakusa and Ueno", "day trip to Nara", "arrival and rest") and the **pace** (`relaxed`, `moderate`, `intense`). Rules:

- the day of arrival, the day of departure and the days with a move between bases are light;
- after a long flight, the first day is `relaxed`;
- place the day trips of the route on the days that suit them, away from moves and not two long day trips in a row;
- spread what is tiring: no more than two `intense` days in a row, and with a `relaxed` profile none at all unless the user asks;
- think of known closures (many museums close one day a week; markets on given days; local holidays) and say they will be checked in phase 6.

Save each day in `days`: `{"date", "base": "<stay id>", "theme", "pace", "items": []}`. `base` is the stay where the night **after** that day is spent: leave it out on the day of departure and on a night spent travelling. Run `check`. Show the overview as a short list and ask for changes. **Stop.**

## 2. The proposals

For each day, or for each zone when several days share it, propose **more things to do than fit** (for example five or six for a day that holds two or three), each in one line: what it is, why it suits these travellers, indicative time needed. Mix the kinds (a museum, a walk, a view, a market, a place to eat when food matters to them), respect what they avoid and their mobility notes.

Before showing them, look the places up:

- run `find-place` with up to ten queries per call, each specific (`"Fushimi Inari Taisha, Kyoto"`), with `--provider <trip.map_provider>`, `--near <lat>,<lon>` of the base, `--country`, `--language` of the trip and `--data "${CLAUDE_PLUGIN_DATA}"`;
- choose the right match (name, address, category); when none fits, try the name in the local language or another wording, and when it is still missing say that the place could not be found;
- save each place in `places`: `{"name", "kind", "lat", "lon", "address", "country", "provider_ids": {"<provider>": "<provider_id>"}}`, with `kind` among `attraction`, `museum`, `nature`, `restaurant`, `city`, `area`, `other`; when the result has `opening_hours`, add `"opening_hours": {"raw": "<as given>", "source": <the source of the search>}`;
- put the ids in the `candidates` of the day (or of every day of the zone).

Run `check`. Show the proposals day by day (or zone by zone) and let the user choose, remove, or add their own (look those up too). **Stop.**

## 3. The detail

For each day, from what the user chose:

- one **main** activity (`"role": "main"`) and one **backup** (`"backup"`), for example indoors in case of rain, or nearby when the main one is closed;
- the **secondary** stops that fit, and **meals** or **rest** when they matter (a long day, children, a famous place to eat);
- stops grouped by zone and in a sensible order: use the coordinates to keep close stops together and avoid going back and forth;
- an indicative `start` time and `duration_min` for each stop, following the pace and what the user avoids (no early start when they avoid early mornings);
- `notes` for what matters on the spot (booking needed, best time to go, a closing day to check).

Do not fill `to_next` (the moves between stops): phase 6 computes them with the map service.

Save the `items` of each day; keep `candidates` as they are. Run `check` and fix every error and every warning about the days you wrote; tell the user about the other warnings that matter. Show the days in a compact form (date, theme, main, backup, the rest in one line) and ask for changes.

When the user agrees:

- `progress.log`: the choices that have a reason worth keeping;
- open points: what is still uncertain (a booking to check, a place not found), with the phase it belongs to (`verification` or `bookings`);
- `progress.phase` → `verification`; `next_step`;
- run `check`.

## 4. Close the phase

Tell the user, in a few lines: the days at a glance, what still needs a booking, and the next step: the verification of places, opening hours and times with the map service.
