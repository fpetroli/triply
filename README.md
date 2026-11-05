# triply

A plugin for Claude that helps you plan and organize your vacations.

> **Status:** early development. The plugin can be installed, but it does nothing yet.

## What it will do

triply guides you from a first idea to a trip that is ready to go:

1. **A guided planning flow.** It asks only what it needs, proposes destinations and routes, builds an overview of the days and then the details, and stops at every step for your choice.
2. **A trip file as the single source of truth.** Every choice, place, booking and deadline lives in one file, so any new session picks up exactly where you left off.
3. **Checked stops.** Each place is checked against real map data: it exists, it is open on that day and at that time, and the travel times between stops are realistic.
4. **Entry requirements.** Passport validity, visas and other requirements are checked on the web, always with source and date.
5. **Ready-to-use documents**, in your language: an itinerary page with a map, a Markdown itinerary, a calendar of booking deadlines, a packing list based on weather and activities.

triply never books or pays for anything: it gives you prefilled search links and keeps track of what you have booked.

You talk to it in plain language — "let's plan a trip to Japan", "I booked the hotel in Kyoto" — and it takes care of the rest.

## Where it runs

- Claude Code
- the Claude desktop app (Cowork)

It does not run on claude.ai in the browser or in the mobile apps, which cannot install plugins.

## Maps and weather

You choose the map service:

- **OpenStreetMap** — no account needed;
- **Mapbox** — free account and token;
- **Google Maps Platform** — free monthly quota; activating a project requires a credit card.

Weather comes from [Open-Meteo](https://open-meteo.com/) (free for non-commercial use).

triply never requires a paid service.

## Your trips folder

triply works in a folder you choose, for example `Trips` on your desktop, with one folder per trip. The files meant for you (itinerary, deadlines, packing list) are at the top of each trip folder, in your language; the files meant for the AI are in a hidden `.triply` folder. triply only rewrites the files it generates and never changes or deletes yours.

## Requirements

- Python 3.9 or later, standard library only: nothing else to install.

## Installation

In Claude Code:

```
/plugin marketplace add fpetroli/triply
/plugin install triply@triply
```

In the Claude desktop app: **Customize → Plugins**, add the marketplace `fpetroli/triply`, then install **triply**.

## Development

- `schemas/trip.schema.json` — the trip file (`.triply/trip.json`);
- `schemas/profile.schema.json` — the user profile, valid for every trip (`.triply/profile.json` in the trips folder);
- `scripts/validate.py` — checks a trip file or a profile against its schema and against the coherence rules (references, dates, planning rules):

  ```
  python3 scripts/validate.py <trip folder | trips folder | file.json> [--json]
  ```

Run the tests from the repository root:

```
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE)
