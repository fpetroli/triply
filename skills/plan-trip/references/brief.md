# Phase 1 — the trip in brief

It turns the user's idea into a trip folder and a trip file with the constraints of the trip.

## 1. One grouped message

Read the profile (`<trips folder>/.triply/profile.json`) and the user's request. Ask, in a single message, **only what you do not know yet**, proposing the profile's values as defaults:

1. **Who comes**: list the people in the profile and ask who travels this time. For anyone new, ask label, age group, citizenship and documents (expiry only), and whether to save them in the profile for future trips.
2. **When**: exact dates, or a period and a length ("two weeks in August").
3. **From where**: default, the usual departure in the profile.
4. **What kind of trip** (sea, cities, nature, culture, food, relax…) and **what to avoid**: default, the profile's preferences.
5. **Destination**: already decided (which), or still open (any idea or limit: "Europe", "within 3 hours of flight", "somewhere warm").
6. **Budget**, optional: an indicative amount, total or per person.
7. **Means of transport** preferred or excluded: default, the profile's.

When the request already answers everything, skip the questions and go on.

## 2. Create the trip

1. **Title**: the destination and the year ("Giappone 2027"); without a destination, the period and the year ("Estate 2027"). It is also the name of the folder: mention it in the closing message, the user can ask to change it.
2. If new people are to be saved in the profile, add them to the profile first and run `check` on the trips folder.
3. Run `new-trip` with the title and `--travellers` with the ids of the people who travel and are in the profile. People who travel but are not saved in the profile are then added to the trip file directly.
4. Fill the trip file (rules: `guide trip-file`):
   - `constraints.origin.name`: the departure;
   - `constraints.dates`:
     - exact dates → `start` and `end`;
     - a period and a length → `window_start`, `window_end` and `length_days` (for example two weeks in August 2027: `2027-08-01`, `2027-08-31`, `14`);
     - unknown → leave `{}` and add an open point;
     - when the user gives no year, take the first future occurrence;
   - `constraints.trip_types`, `constraints.avoid`, `constraints.transport_preferences`, `constraints.budget` (`amount`, `currency`, `scope`: `total` or `per_person`);
   - a decided destination → one entry in `options`: `{"id": "<slug>", "kind": "destination", "title": "<destination>", "chosen": true}`;
   - `progress.log`: one entry per choice of this phase that has a reason worth keeping ("dates: second half of August — school holidays");
   - `progress.open_points`: what is still uncertain;
   - `progress.phase`: `destination` if the destination is still open, otherwise `entry_requirements`;
   - `progress.next_step`: one sentence on what comes next.
5. Run `check` on the trip folder. Fix every error. Tell the user about the warnings that matter to them, in plain words (for example a passport that expires before the end of the trip).

## 3. Close the phase

Tell the user, in a few lines:

- the folder created, by name and where it is;
- the summary of the trip: who, when, from where, what kind of trip, destination or what is still open, budget;
- the open points, if any;
- the next step.

The next phases are not available yet: say plainly that this version of triply stops here, that everything is saved, and that the next version will continue from this point.
