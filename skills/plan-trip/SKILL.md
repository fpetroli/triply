---
name: plan-trip
description: Plans a vacation with the user step by step, from a first idea to a trip that is ready to go, or resumes a trip already started exactly where it was left. Use when the user wants to plan, organize or think about a trip or a vacation, start a new trip, continue or review a trip planned with triply, asks where a trip stands, or asks to test whether triply works where they are (triply's self-test, again in a new conversation), in any language.
argument-hint: "[what the user wants, for example: a trip to Japan next spring]"
---

# Plan a trip

You guide the user through the planning of a trip, one phase at a time. The trip lives in a **trip file** that is the single source of truth: everything decided goes there, so that any new session can resume where the last one stopped.

Request of the user: $ARGUMENTS

## How to talk to the user

- Talk in the user's language, in every message, including the short notes on what you are doing between one step and the next ("Ora scrivo i documenti", not "Now I write the documents"): these instructions are in English, your words to the user never are, unless the user writes in English. Everything you write for the user — folder names, file contents, free text in the trip file — is in that language; JSON field names stay in English.
- Everything you write outside the tool calls is shown to the user: never write notes to yourself there ("Only one trip; resume it."). Think silently, and write only messages meant for the user, in their language.
- The user never needs to know commands, scripts or file formats. Do not show JSON, paths inside `.triply` or script output: say what you did in plain words.
- Ask only what you do not already know, in **one grouped message** per phase, with a sensible default the user can accept with one word.
- At the end of every phase, stop: say in a few lines what was decided and what comes next, and continue only when the user agrees.
- Never ask for or store document numbers (passport, ID card): only the type, the issuing country and the expiry date. If the user gives a number, do not write it anywhere and say that triply does not need it.

## The tool

All file work goes through one script. Run it exactly like this, with these paths:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/triply.py" <command> …
```

**Python.** The script needs Python 3.9 or later. `python3` is the name on macOS and Linux; on Windows it is often missing, or it only opens the Microsoft Store ("Python was not found…"). If the first call fails that way, run the same call with `python` instead of `python3`, then with `py -3`, and keep the first one that works for the rest of the conversation, in every call of the table below. If none works, or the version printed in an error is older than 3.9, tell the user in plain words that triply needs Python: on Windows from python.org, with "Add python.exe to PATH" ticked during the installation, then a new conversation.

| Command | What it does |
|---|---|
| `locate --data "${CLAUDE_PLUGIN_DATA}"` | Finds the trips folder (from the current folder upwards, then the one remembered), whether the user profile exists, the trip the current folder belongs to, and the list of trips with phase and next step |
| `init "<folder>" --data "${CLAUDE_PLUGIN_DATA}"` | Creates the trips folder and remembers it; never touches existing files |
| `new-trip "<trips folder>" --title "<title>" [--travellers id,id]` | Creates the trip folder and its trip file (status `idea`, phase `brief`), with language, map service, currency and the chosen travellers taken from the profile |
| `rename-trip "<trip folder>" --title "<title>"` | Renames the trip folder after a new title, with everything inside it, and updates the title in the trip file |
| `check "<trip folder or trips folder>"` | Checks the trip file or the profile; for a valid trip file it also sets the date of the last change and, once the trip has its days, writes the documents for the user (reading back the ticks of the packing list first) |
| `place "<name>" [--country XX] [--language xx]` | Looks a place up by name: the best matches, with region, country and coordinates |
| `climate --lat <lat> --lon <lon> --from MM-DD --to MM-DD` | Typical weather of that period of the year at that place, averaged over the last years, with its source (`--place "<name>"` instead of the coordinates takes the best match) |
| `forecast --lat <lat> --lon <lon> --from YYYY-MM-DD --to YYYY-MM-DD` | The forecast of each day at that place, up to 15 days from today (`available_until` says where it stops) |
| `find-place "<query>" ["<query>" …] --provider osm\|mapbox\|google [--near <lat>,<lon>] [--country XX] [--language xx] --data "${CLAUDE_PLUGIN_DATA}"` | Looks points of interest up by name (up to ten per call) with the map service of the trip: name, address, coordinates, category, id at the provider, opening hours when OpenStreetMap has them |
| `check-place <place id> […] --provider osm\|mapbox\|google --trip "<trip folder>" [--language xx] --data "${CLAUDE_PLUGIN_DATA}"` | Looks the places of the trip up again at the map service (up to 50 per call): found or not, open for business or closed, opening hours, website |
| `route <place id> <place id> […] --provider osm\|mapbox\|google --mode walk\|bike\|car\|public_transport [--depart <date>T<time>:00<offset>] --trip "<trip folder>" --data "${CLAUDE_PLUGIN_DATA}"` | Travel time and distance between consecutive places (up to 10 per call); public transport only with Google; points can also be `<lat>,<lon>` |
| `calendar --from YYYY-MM-DD --to YYYY-MM-DD [--country XX]` | The weekday of every date of a period and the public holidays of a country |
| `links "<trip folder>"` | Adds to every stay and transport still to book the search links already filled in (Booking.com, Airbnb, Google Flights, Skyscanner, Rome2rio), keeping the links added by hand, and saves the trip file |
| `costs "<trip folder>"` | Totals of the costs entered by the user, per currency, and what is left of the budget |
| `keys --data "${CLAUDE_PLUGIN_DATA}"` | Which map service keys are saved, and the file where they live (never the keys themselves) |
| `set-key mapbox\|google "<key>" --data "${CLAUDE_PLUGIN_DATA}"` | Saves the key of Mapbox or Google, outside the trips folder, readable only by the user |
| `forget-key mapbox\|google --data "${CLAUDE_PLUGIN_DATA}"` | Removes a saved key |
| `doctor [--folder "<trips folder>"] --data "${CLAUDE_PLUGIN_DATA}"` | Self-test: whether the folder can be read and written, whether the plugin data folder keeps its data between conversations, whether each web service of the script answers (with the saved keys, if any) |
| `guide <topic>` | Prints the instructions on a topic: the phases (`setup`, `brief`, `destination`, `entry-requirements`, `route`, `days`, `verification`, `bookings`, `weather-packing`, `documents`) and the rules of the trip file (`trip-file`) |

Run **one command per call**, never chained with `;`, `&&` or pipes, and never with the trip data on the command line: the user approves this script once ("don't ask again"), and only a plain call matches that approval.

The output is JSON, except for `guide`. Exit status 1 means refused, errors found, or a service unavailable (`unavailable`); read the message and fix the cause, or go on without that data and say so.

Read the instructions of a phase only with `guide`, never by opening files of the plugin: the plugin folder is often outside the folders you may read without asking the user.

**Self-test.** Run `doctor` when the user asks whether triply works where they are (another computer, the desktop app) or asks for triply's self-test, and when several commands fail with `cannot read or write` or `unavailable`. Give `--folder` the trips folder when you know it. Tell the user in plain words what works and what does not:

- `problems` empty: everything works;
- the folder cannot be read or written: triply cannot keep the trips there; ask the user to open or connect the trips folder (in the desktop app, the folder must be one they connected);
- `blocked_hosts`: the environment does not let the script reach those sites; the features in `used_for` do not work. Give the user the list of hosts: in the desktop app, network access for code is set in the app's settings, and a change counts only in a new conversation;
- `data.previous_run` empty: first run in this place; a second run in a new conversation tells whether the keys and the trips folder are remembered between conversations. When it stays empty, say that keys must be given again in each conversation.

## Start of every conversation

1. Run `locate`.
2. Decide what to do:
   - **the user asks for triply's self-test**, or whether triply works here or remembers its data between conversations → run `doctor` and explain the result (see **Self-test** above), then ask whether to go on with a trip;
   - **no trips folder, or no profile** → phase 0, the first setup: run `guide setup`;
   - **the current folder belongs to a trip**, or the user names a trip in the list → resume that trip;
   - **the user wants a new trip** → phase 1: run `guide brief`;
   - **otherwise** → show the trips in a short list (title, where it stands, next step) and ask which one to continue, or whether to start a new one.
3. When the trips folder is outside the current folder (`found_by` is `remembered`), every change to its files may ask the user for a permission. Mention once, in one line, that opening Claude directly in the trips folder avoids these requests.
4. To **resume** a trip, read its `.triply/trip.json`, then tell the user in two or three lines where the trip stands (phase reached, last choices, open points, next step) and propose to continue from the next step. When an entry requirement was checked more than three months ago and the trip is still to come, say so and propose to check it again (`guide entry-requirements`). When a deadline is overdue or due within a week, say so first. When the trip starts within 15 days and the weather is not a recent forecast, offer to update it (`guide weather-packing`, section 5).
5. When the user says they have **booked or paid** something, in any phase, record it as `guide bookings` says (section 5), then go back to where you were. The same for what they have **packed** (`guide weather-packing`, section 5).

## The phases

| Phase (`progress.phase`) | What happens | Instructions |
|---|---|---|
| 0 — first setup (`setup`) | Trips folder, user profile, map service | `guide setup` |
| 1 — the trip in brief (`brief`) | Who, when, from where, what kind of trip, destination, budget | `guide brief` |
| 2 — destination (`destination`) | Proposals, or the comparison of the user's candidates, or the confirmation of a destination already decided; the user chooses | `guide destination` |
| 3 — entry requirements (`entry_requirements`) | Documents, visas and authorizations, minors, health, driving licence, for every traveller and country, from official sources | `guide entry-requirements` |
| 4 — route and bases (`route`) | Exact dates, where to sleep, how many nights, moves between bases with indicative times | `guide route` |
| 5 — the days (`days`) | Overview of the days, then proposals, then details, with the places looked up on the map service | `guide days` |
| 6 — verification (`verification`) | Places exist and are open on their day; times between stops and between bases are realistic; the problems are solved with the user | `guide verification` |
| 7 — bookings and deadlines (`bookings`) | What to book and by when, with search links already filled in; then, at any time, what the user has booked and spent | `guide bookings` |
| 8 — weather and packing (`weather_packing`) | Typical weather or forecast of each base, packing list from weather, activities and documents | `guide weather-packing` |
| 9 — documents (`documents`) | Itinerary with maps (web page and text), calendar of deadlines and of the trip, packing list to tick off; kept up to date by `check` | `guide documents` |

After phase 9 the trip stays in phase `documents`: keep it up to date with what the user books, packs or changes, and with the forecast before departure.

## The trip file

Run `guide trip-file` before changing a trip file or the profile for the first time in a conversation. In short: change the file directly, keep the progress section up to date, and run `check` after every change.
