# Phase 6 — the verification

It checks the days of phase 5 against real data, and shows the user **only the problems**, each with a proposal to solve it. It checks:

1. that every place **exists** and is **open** on its day and at its time, with the weekly closing days and the public holidays;
2. that the **times between the stops** of each day are realistic;
3. the **moves between bases** estimated in phase 4.

Every fact checked is saved with its source and the date, **as soon as it is checked**, day by day, before showing the problems: if the conversation stops, nothing is lost. Only the changes to solve the problems wait for the user's yes. The work is long: tell the user in one line what you are about to check, and give short progress notes in their language (for example "day 3 of 12 checked").

## 0. Before you start

- Read the trip file: dates, days, places, stays, transports, travellers (mobility notes, children, pace), constraints (transport preferences, car rental).
- The map service is `trip.map_provider`. With `mapbox` or `google`, run `keys`; when the key is missing or refused, handle it as in phase 5 (`guide days`, section 0).
- With `google`, mention once that checking opening hours uses a costlier tier of Google, with a smaller free monthly quota (about 1,000 places a month), largely enough for one trip.

## 1. The calendar

Run `calendar --from <first day> --to <last day> --country <country>` for every country of the trip. It gives the **weekday** of every date (never work it out yourself) and the public holidays. Keep both at hand for the next step:

- a holiday can close museums and shops, change the timetables of trains and buses, or make a place very crowded;
- regional holidays count only in their regions;
- the holidays come from an open dataset: when a holiday changes a plan (a closure, a day to move), confirm it on an official source, as in section 2.

## 2. The places

**With the map service.** Run `check-place` with the ids of the places of the days (`--trip "<trip folder>"`, up to 50 ids per call, `--provider <trip.map_provider>`, `--language` of the trip). For each place:

- `found: false`: the place may be gone or have moved; look it up again with `find-place` and tell the user;
- `status` other than `open` (closed temporarily or for good, opening in the future): it is a problem;
- `without_id`: the place has no id at this provider (for example the map service was changed): look it up with `find-place` first and save the id;
- an `error` on a place: try again later, or check it on the web.

**On the web, with more than one source.** For the stops that matter — the **main** activity and the **backup** of each day, every place that needs a ticket or a booking, and every place whose hours are missing or unclear — check opening hours, closing days, seasonal hours and last entry on the web:

- first the **official site** of the place (the museum, the park, the temple, the operator), which the map service often gives as `website`; then **at least one other independent source** (the city or the region's tourism office, OpenStreetMap when the map service is another one, a guide published by a public body);
- the hours of the travel dates, not of today: many places have summer and winter hours, and some close for works or for a season;
- **sources agree** → `ok`; save the official one as `source` and the others in `confirmed_by`;
- **sources disagree** → the official and most recent one wins: `ok`, with a note that says what disagreed, and you tell the user; when no official source settles it, `warning`, with the note;
- **only one source found** → `ok` when it is the official site of the place; otherwise `warning`, with the note "one source only";
- never get around a site that blocks automatic reading; when a site cannot be read, use the other sources and say so.

For the other stops (secondary stops, meals) the map service is enough; when it has no hours, write it in the notes of the stop.

**What to save.**

- On the place: `opening_hours` `{"raw", "source", "confirmed_by", "notes"}` and `verification` `{"status", "checked_at", "notes", "sources"}`, with `status` `ok`, `warning` or `failed` (gone, closed for good).
- On each stop of a day: `verification` `{"status", "checked_at", "notes"}` — whether the place works **on that day at that time**: open on that weekday, not closed for a holiday, the visit ends before closing time (and before the last entry). A place open in general but closed that day is `failed` on the stop, not on the place.

## 3. The times between the stops

For each day, compute the moves between consecutive stops with `route` and the place ids of the trip (`--trip`, up to 10 points per call, in the order of the day):

- choose the **mode** for each move: on foot for short moves (about 20–25 minutes of walking, less with children, older travellers or mobility notes); otherwise public transport, or the car when the trip has a car;
- **public transport** is computed only with `google` (`--mode public_transport --depart <date>T<time>:00<offset>`, with the start of the move and the time offset of the place on that date). When Google finds no route for a date far ahead (timetables are often published a few months before), try the same weekday and time in the next weeks and say in `notes` that it comes from the current timetable;
- with `osm` or `mapbox`, or when Google finds nothing: take the walking time and the distance; if walking is too long, estimate the public transport time from the journey planner of the local operator on the web, with its source, or as an estimate (`"estimated": true`) when there is none. Say in `notes` which line or kind of transport;
- car times from `osm` have no traffic: in towns and at rush hours, add a margin and say so in `notes`.

Save each move on the stop it leaves from: `to_next` `{"mode", "minutes", "distance_km", "source", "notes"}` (or `"estimated": true` without a service). The last stop of a day has no `to_next`.

Save the moves of each day, then run `check`: it warns when a stop starts before the previous stop and the move are over ("minutes missing"). Look also at the whole day: does it hold with the pace of the day and of the travellers, with the meals, and with the way back to the base?

## 4. The moves between bases

For each transport with `"duration_estimated": true`, except flights:

- **car**: `route --mode car` between the two places; add a margin for stops on a long drive;
- **flight**: the duration is known when the flight is chosen, in the bookings: keep the estimate;
- **train, bus, ferry, flight**: on the web, the **official site of the operator** (the railway company, the ferry company, the airline) or the national journey planner, and **a second independent source**; the same rules as for opening hours (agree, disagree, one source). Look at the travel date: some lines run only on given days or seasons. When the timetable for that date is not published yet, use the current timetable for the same weekday and say so in `notes`;
- with `google` and public transport, `route --mode public_transport` is one of the sources.

Save `duration_min`, `duration_source`, `duration_confirmed_by` and remove `duration_estimated`. Add `depart_time` and `arrive_time` only for a connection the user will actually take; the choice of the exact connection belongs to the bookings. When the new time changes the day (a much longer move, a ferry only in the afternoon), it is a problem.

## 5. The problems

Run `check`. Collect the problems: places gone or closed, stops that do not work on their day, days that do not hold, moves much longer than planned, sources that disagree. If there are none, say so in one line.

Show them **all together**, grouped by day, each in one or two lines with **one proposal** to solve it, for example:

- swap two days (when the swap respects the bases and the rules of phase 5);
- use the backup activity;
- change the order of the stops, or the start time;
- take another means of transport;
- drop a stop to lighten a day.

Ask the user to accept the proposals or to change them. **Stop.** Then apply what is agreed, check again what changed (places, moves, `check`) and show only what is still open.

## 6. Close the phase

When the user agrees:

- `progress.log`: the changes made and their reason;
- open points: what is still uncertain (a timetable not published yet, a source that disagrees, a holiday to confirm), with its phase (`bookings`, or `verification` for what must be checked again later);
- `progress.phase` → `bookings`; `next_step`;
- run `check` and fix every warning about what is not verified yet.

Tell the user, in a few lines: what was checked, what changed, what remains uncertain, and the next step: what to book and by when.
