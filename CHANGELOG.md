# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Plugin skeleton: manifest, marketplace file, folder layout, MIT licence.
- Trip file schema (`schemas/trip.schema.json`) and user profile schema (`schemas/profile.schema.json`).
- `scripts/validate.py`: checks a trip file or a user profile against its schema and the coherence rules; standard library only, Python 3.9 or later.
- Tests for the checks.
- `plan-trip` skill: finds or resumes a trip, first setup (trips folder, user profile, map service) and the trip in brief (who, when, from where, kind of trip, destination, budget).
- `scripts/triply.py`: single entry point of the skill — finds and creates the trips folder, creates and renames a trip, checks a file, looks a place up, gives the climate of a period (Open-Meteo), prints the instructions of a phase.
- Phase 2 of the planning flow, the destination: proposals, comparison of the user's candidates or confirmation of a destination already decided, with the climate of the period from Open-Meteo.
- `rain_days` in the weather entries of the trip file.
- Phase 3 of the planning flow, the entry requirements: documents, visas and authorizations, transit, minors, health and driving licence for every traveller and country, from official sources only, with deadlines and a new check before departure.
- Entry requirements in the trip file: `kind`, `mandatory` and `check_url`; the source is required unless the status is `unknown`. The check warns about requirements still to do or not verified, and about checks older than three months.
- Phase 4 of the planning flow, the route and the bases: exact dates, bases and nights, moves between bases with indicative times, following rules of realism.
- Transports in the trip file: `duration_estimated`, `duration_source` and `notes`. The check warns about nights without a stay, a single night in the middle of the trip, and a duration with no source.
- Phase 5 of the planning flow, the days: overview, proposals with the places looked up on the user's map service, then the detail of each day with a main activity and a backup.
- `find-place`: points of interest by name with OpenStreetMap (Nominatim), Mapbox (Search Box) or Google (Places API, New).
- `keys`, `set-key`, `forget-key`: the keys of Mapbox and Google, kept in the plugin data folder, never in the trips folder.
- Phase 6 of the planning flow, the verification: places found again and open on their day, opening hours cross-checked on more than one source, times between stops and between bases, problems solved with the user.
- `check-place`: places looked up again by id with OpenStreetMap (Nominatim lookup), Mapbox (Search Box retrieve) or Google (Place Details, with opening hours).
- `route`: travel times with OpenStreetMap (OSRM servers of FOSSGIS), Mapbox (Directions) or Google (Routes API, also public transport).
- `calendar`: weekdays and public holidays of a period (Nager.Date).
- Phase 7 of the planning flow, bookings and deadlines: what to book and by when, with search links already filled in and official sites; then, at any time, what the user has booked and spent.
- `links`: search links for stays (Booking.com, Airbnb), flights (Google Flights, Skyscanner) and trains, buses and ferries (Rome2rio), with no affiliate code.
- `costs`: totals of the costs per currency and what is left of the budget.
- Phase 8 of the planning flow, weather and packing: typical weather of each base, then the forecast in the last 15 days; one packing list for the trip from weather, activities and documents, with the reason of each item.
- `forecast`: the forecast of each day at a place, up to 15 days ahead (Open-Meteo).
- Phase 9 of the planning flow, the documents: itinerary as a web page with maps (OpenFreeMap and MapLibre GL JS, no key) and as Markdown, calendar with the deadlines (two reminders each), the stays and the moves, packing list with checkboxes. `check` writes them after every change once the trip has its days, as a draft until the verification; it reads back first the ticks changed in the packing list, and never overwrites a file the user made. File names and fixed texts in English and Italian; for other languages Claude writes the translation once in the trip folder.
- Trip file: `rain_probability_pct` in the weather, `traveller` and `source` on packing items. The check warns when the forecast is available but not used yet, or more than two days old.
- Trip file: `booking.links`, `booking` on the stops of the days, `iata` on places, `source` on deadlines and the deadline kind `cancellation`. The check warns about overdue deadlines, deadlines of things already booked, things still to book with no deadline after this phase, and a budget exceeded.
- Trip file: `verification` of each stop of a day, `confirmed_by` and `notes` on opening hours, `sources` on the verification of a place, `duration_confirmed_by` on transports, `estimated` and `notes` on the moves between stops. The check warns when there is not enough time between two stops, about stops and places to review, and, after the verification, about what is still unchecked.
