# triply

A plugin for Claude that helps you plan and organize your vacations.

> **Status:** early development, not released yet. Every phase of the planning is there, from the first setup to the documents of the trip. It is tested in Claude Code, not yet in the Claude desktop app.

## What it does

triply guides you from a first idea to a trip that is ready to go:

1. **A guided planning flow.** It asks only what it needs, proposes destinations and routes, builds an overview of the days and then the details, and stops at every step for your choice.
2. **A trip file as the single source of truth.** Every choice, place, booking and deadline lives in one file, so any new session picks up exactly where you left off.
3. **Checked stops.** Each place is checked against real map data: it exists, it is open on that day and at that time, and the travel times between stops are realistic.
4. **Entry requirements.** Passport validity, visas and other requirements are checked on the web, always with source and date.
5. **Ready-to-use documents**, in your language: an itinerary page with maps, a Markdown itinerary, a calendar with the deadlines, the stays and the moves, a packing list based on weather and activities.

triply never books or pays for anything: it gives you prefilled search links and keeps track of what you have booked.

You talk to it in plain language — "let's plan a trip to Japan", "I booked the hotel in Kyoto" — and it takes care of the rest.

## Where it runs

- Claude Code
- the Claude desktop app (Cowork)

It is made for macOS, Linux and Windows. It does not run on claude.ai in the browser or in the mobile apps, which cannot install plugins.

The desktop app and Windows are not tested yet. To check that triply works where you use it, ask Claude: "run triply's self-test". It checks that your trips folder can be written, that triply remembers its settings between conversations, and that it can reach the web services it uses, and tells you what to change if something is blocked.

## Maps and weather

You choose the map service:

- **OpenStreetMap** — no account needed;
- **Mapbox** — free account and token;
- **Google Maps Platform** — free monthly quota; activating a project requires a credit card.

Weather comes from [Open-Meteo](https://open-meteo.com/) (free for non-commercial use): the average of the last years, then the forecast in the last 15 days before departure.

triply never requires a paid service.

With Mapbox or Google, triply asks for the key the first time it looks places up, and keeps it in the plugin's own data folder on your computer, readable only by you and outside your trips folder, so it never ends up in a trip you share. Use the Mapbox *public* token (`pk.…`); for Google, a key restricted to the Places API (New) and the Routes API. If you prefer not to paste the key in the chat, triply tells you which file to write it in. Uninstalling the plugin removes that folder, and the keys with it.

To check the days, triply asks the map service for the travel times and looks the places up again. With OpenStreetMap, routes come from the public routing servers of [FOSSGIS](https://routing.openstreetmap.de/) (on foot, by bike, by car; car times have no traffic); public transport is computed only by Google. With Google, checking opening hours uses the "Enterprise" tier of Place Details, which has a smaller free monthly quota (1,000 places at the time of writing): enough for a trip, but keep an eye on it in the Google Cloud console. Public holidays come from [Nager.Date](https://nagerholidays.com/).

For what to book, triply prepares links that open Booking.com, Airbnb, Google Flights, Skyscanner and Rome2rio with places, dates and travellers already filled in, next to the official sites. triply never queries these sites, never sees prices and never books; the links carry no affiliate code. These sites do not document their link format: if one changes, the link still opens the site, perhaps without the data filled in.

With OpenStreetMap, place and route data is © OpenStreetMap contributors ([fix the map](https://www.openstreetmap.org/fixthemap)).

## The documents

In each trip folder, in your language, kept up to date after every change from the moment the days are planned:

- the itinerary as a web page with maps, to open in the browser, and as text (Markdown);
- a calendar file (`.ics`) to import into Google, Apple or Outlook calendar: every deadline with two reminders, the stays and the moves between bases;
- the packing list with checkboxes: tick them in any editor, and triply reads them back.

The maps of the itinerary use [OpenFreeMap](https://openfreemap.org/) (OpenStreetMap data, no key) with [MapLibre GL JS](https://maplibre.org/), loaded from unpkg; they need an internet connection, the rest of the page does not. A Mapbox or Google key never goes into these files, which you may share.

## Your trips folder

triply works in a folder you choose, for example `Trips` on your desktop, with one folder per trip. The files meant for you (itinerary, deadlines, packing list) are at the top of each trip folder, in your language; the files meant for the AI are in a hidden `.triply` folder. triply only rewrites the files it generates and never changes or deletes yours.

## Requirements

- Python 3.9 or later, standard library only: nothing else to install.
- On macOS and Linux Python is usually there already. On Windows, install it from [python.org](https://www.python.org/downloads/) and tick "Add python.exe to PATH" during the installation; triply finds it whether it is called `python3`, `python` or `py`.

## Installation

In Claude Code:

```
/plugin marketplace add fpetroli/triply
/plugin install triply@triply
```

In the Claude desktop app: **Customize → Plugins**, add the marketplace `fpetroli/triply`, then install **triply**.

## Permissions

triply works through one script of its own, `scripts/triply.py`, which finds and creates your trips folder, checks the trip files, writes the documents and asks the web services above (Open-Meteo, the map service, Nager.Date). The first time, Claude asks your permission to run it: choose **"Yes, and don't ask again"**. After an update of the plugin it may ask once more.

triply asks to keep your trips folder inside the folder where you open Claude, and next time to open Claude directly there: that way changes to the trip files do not ask for permission one by one.

To check the entry requirements, Claude searches the web and reads the official pages (foreign ministries, embassies, immigration authorities, the European Union): Claude asks your permission for web search and for each site the first time. Some official sites cannot be read automatically; triply then gives you the links to check by hand and records what you read.

To check opening hours and timetables, Claude reads the official site of the place or of the operator and at least one other source, to cross-check them; again, Claude asks your permission for each site the first time.

## Development

- `schemas/trip.schema.json` — the trip file (`.triply/trip.json`);
- `schemas/profile.schema.json` — the user profile, valid for every trip (`.triply/profile.json` in the trips folder);
- `skills/plan-trip/` — the planning skill: `SKILL.md` and the instructions of each phase in `references/`;
- `scripts/triply.py` — the single entry point the skill uses: find and create the trips folder, create and rename a trip, check a file, look a place up, get the climate of a period, look points of interest up and check them again, compute travel times, give weekdays and public holidays, give the forecast, prepare the search links, total the costs, keep the map service keys, run the self-test, print the instructions of a phase;
- `scripts/climate.py` — places, climate and forecast from [Open-Meteo](https://open-meteo.com/) (geocoding, historical weather, forecast);
- `scripts/places.py` — points of interest by name with OpenStreetMap (Nominatim), Mapbox (Search Box) or Google (Places API, New), and their check by id;
- `scripts/routes.py` — travel times with OpenStreetMap (OSRM servers of FOSSGIS), Mapbox (Directions) or Google (Routes API);
- `scripts/calendar_days.py` — weekdays and public holidays (Nager.Date);
- `scripts/bookings.py` — search links already filled in, and the costs of a trip;
- `scripts/doctor.py` — the self-test: folder, plugin data, web services;
- `scripts/documents.py` — the documents for the user: itinerary (HTML and Markdown), calendar (iCalendar), packing list;
- `scripts/validate.py` — checks a trip file or a profile against its schema and against the coherence rules (references, dates, planning rules):

  ```
  python3 scripts/validate.py <trip folder | trips folder | file.json> [--json]
  ```

Run the tests from the repository root (on Windows, `python` or `py` instead of `python3`):

```
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE)
