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
