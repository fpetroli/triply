# The trip file and the user profile

- **Trip file**: `<trip folder>/.triply/trip.json` — the single source of truth of one trip.
- **User profile**: `<trips folder>/.triply/profile.json` — the data valid for every trip.

Use only the fields shown in these instructions and in the examples of the phases. The check refuses any field or value it does not know and says exactly which one and what is allowed.

## How to change them

- Change the file directly: small edits for small changes, never a rewrite from memory of a large file.
- After **every** change run `check`. Errors make the file unusable: fix them at once, never leave a file with errors. Warnings are things to review: tell the user about those that matter to them.
- Write only inside `.triply/`. The files of the user in the trips folder and in the trip folders are never changed, moved or deleted.

## Values

- **ids**: lower-case letters, digits and hyphens (`anna`, `kyoto-station`), unique in their list.
- **dates**: `YYYY-MM-DD`; **times**: `HH:MM`.
- **countries**: two capital letters, ISO 3166-1 (`IT`, `JP`); **currencies**: three capital letters (`EUR`, `JPY`); **language**: `it`, `en`, `pt-BR`.
- **free text** (labels, interests, choices, reasons, next step): in the user's language.
- **people**: `age_group` is `infant`, `child`, `teen`, `adult` or `senior`; **pace** is `relaxed`, `moderate` or `intense`.
- **means of transport**: `flight`, `train`, `ferry`, `bus`, `car`, `car_rental`, `other`.
- **documents**: `type` (`passport`, `id_card`, `visa`, `driving_licence`, `other`), `country`, `expires`. Never a number.
- **costs**: only what the user says; never invent prices.
- **data from outside** (opening hours, travel times, requirements, weather): always with its `source` (service, link, date of consultation).
- **entry requirements**: `kind` is `document`, `visa`, `transit`, `minors`, `health`, `driving` or `other`; `status` is `ok`, `action_needed` or `unknown`; a `source` is required unless the status is `unknown`.
- **travel times**: a `duration_min` estimated by you has `"duration_estimated": true`; once checked with the map service it has `duration_source` instead.

## The progress section

`progress` is what lets a new conversation resume. Keep it up to date at the end of every phase and whenever something is decided:

- `phase`: the phase the trip is in now, that is the next one to work on;
- `next_step`: one sentence on what to do next;
- `open_points`: what is still uncertain — `{"id", "text", "phase", "created"}`; remove a point when it is resolved, recording the outcome in the log;
- `log`: the choices made, oldest first, never rewritten — `{"date", "phase", "choice", "reason"}`.

The trip's `status` is `idea` until the route is chosen, then `planning`; `booked` when the user says the main bookings are done.

## Travellers

The trip keeps its own copy of its travellers. When the user changes the data of a person (for example a new passport), update the profile and the trips that are not completed or cancelled, and say so.
