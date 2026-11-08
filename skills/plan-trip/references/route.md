# Phase 4 — route and bases

It turns the destination into a route: where the travellers sleep, how many nights in each base, how they move between bases, and the exact dates of the trip.

Travel times in this phase are **indicative estimates**: say so every time you give one. Phase 6 checks them with the map service and may correct them.

## 1. Where the user starts from

Read the trip file: constraints (dates, origin, pace, means of transport, what to avoid, budget), the chosen destination, the `route` options, the open points of phase `route`, the entry requirements still to do.

| The user has… | What you do |
|---|---|
| **a trip in mind** (an option of kind `route`, or places named now) | keep it: propose the nights for each base, the order and the moves; point out only real problems against the rules below, and say why |
| **only the destination** | two or three different routes, for example one base with day trips, or two or three bases in a row |

Never replace the user's route with yours: propose changes only when asked or when the route breaks a rule below.

Ask, in one grouped message, only what is missing:

- the **exact dates**, when the trip still has a window: propose dates that fit the window and the length, and say why (for example "back before Golden Week"). The route cannot be fixed without them;
- **arrival and departure**: the same airport or station, or arriving in one place and leaving from another (often shorter and cheaper on a line route);
- places the user wants or does not want, when it is not clear.

## 2. Rules of realism

- **At least two nights per base**; three or more with a `relaxed` pace. A single night is fine only at the start or at the end, for example near the airport.
- **No change of base every other day**: on a long trip, few bases and day trips from them are better than many moves.
- A day with a **long move** (more than about three hours door to door) has little else in it.
- **After a long flight** (more than about six hours, or across many time zones) the first day is light; when the flight arrives late in the evening, the first day of visits is the next one.
- **Day trips**: a place that does not need a night (a town nearby, an excursion) is a day trip from a base; say from which base and how long the return trip takes. Day trips are planned in phase 5.
- Respect the constraints: the means of transport preferred or excluded, what to avoid (for example "early mornings" means no move that starts at dawn), the budget (fewer moves and fewer bases cost less).
- Count nights exactly from the dates: a trip from 2027-04-05 to 2027-04-19 has 14 nights, minus the nights spent on a plane or on an overnight ferry.

## 3. Each route proposal

For every route, in five to eight lines:

1. the **bases**, in order, with the nights in each;
2. the **moves** between bases: means of transport and indicative duration ("about 2 hours 15 by high-speed train, indicative"), including the outward and return journey from the origin;
3. the **day trips** possible from each base;
4. why it fits these travellers, and its pros and cons.

Then one line comparing the routes. Save them **before** asking: one entry in `options` per route — `"kind": "route"`, `title`, `summary` (bases with nights, moves, day trips), `pros`, `cons`, `"chosen": false`. The user's own route is updated in place, not duplicated. Run `check`.

## 4. When the user chooses

1. **Dates**: in `constraints.dates`, replace the window with `start` and `end` (remove `window_start`, `window_end` and `length_days`); write the choice and its reason in the log. Move the deadlines that were counted from the window (for example the new check of the entry requirements, about 30 days before departure) to the new dates.
2. In `options`: `"chosen": true` on the chosen route, with its final `summary`.
3. In `places`: every base, with `place` for the coordinates — `{"name", "kind": "city" or "area", "lat", "lon", "country"}` — and the origin if it is not there yet (then set `constraints.origin.place` to its id). Add arrival and departure airports, stations or ports only when they are known.
4. In `stays`: one per base — `{"id": "stay-<base>", "place": "<base id>", "check_in", "check_out", "booking": {"status": "to_book"}}`. Consecutive stays share the date: the `check_out` of one is the `check_in` of the next, unless the night is spent travelling.
5. In `transports`: every move between bases, the outward and the return journey — `{"id", "mode", "from", "to", "date", "duration_min", "duration_estimated": true, "notes", "booking": {"status": "to_book"}}`. Use `notes` for a stopover or a choice still open ("probably via Istanbul"). A move with no booking (a car already rented, a local bus) has `"status": "not_needed"`.
6. `trip.status` → `planning`.
7. In `progress`: the log entries (route, dates, nights, with their reasons); close the open points that are resolved; add an open point for what is still uncertain; the open points about day trips get `"phase": "days"`; `phase` → `days`; `next_step`.
8. Run `check` and fix every error. Tell the user about the warnings that matter (a night without a stay, a single night in the middle of the trip, a stay outside the dates).

## 5. Close the phase

Tell the user, in a few lines: the route with nights per base, the dates, the moves with their indicative times, the day trips planned for later, what is still to do (bookings come in phase 7, after the days), and the next step: the overview of the days.
