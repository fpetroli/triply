# Phase 2 — the destination

It brings the user to a chosen destination, whatever they start from: no idea at all, a few candidates, a destination already decided, or a whole trip already in mind.

## 1. Where the user starts from

Read the trip file: constraints, `options`, `progress.log`, open points. Then:

| The user has… | What you do |
|---|---|
| **no idea** | three proposals that fit the constraints |
| **a few candidates or an idea** ("Sardinia or Corsica", "a Greek island") | compare those candidates; add at most one alternative of your own, and say it is yours |
| **a destination decided** (an option with `chosen: true`) | one card for that destination, to confirm it: climate, how to get there, first notice on documents; no alternatives unless asked |
| **a whole trip in mind** (places, stops, an order) | keep it as it is: it is an option of kind `route` (saved in phase 1, or save it now); the destination is the area it covers. Mention only real problems against the constraints (for example far too many stops for the days); the route itself is worked on in phase 4 |

Never replace the user's idea with yours: propose alternatives only when asked or when the idea clashes with a hard constraint (documents, dates, budget), and say why.

## 2. Build each card

For every destination:

1. **Climate of the period.** Choose a representative place: the main town, or where they would stay. Run `place "<name>"` when the name may be ambiguous, then `climate --lat <lat> --lon <lon> --from <MM-DD> --to <MM-DD>`, with the trip's dates (`start` and `end`) or, for a flexible period, `window_start` and `window_end`. Give mean maximum and minimum, rainy days in the period, and say it is the average of the last years from Open-Meteo. If the service is unavailable, give your estimate and say plainly that it is an estimate, not verified.
2. **How to get there** from the departure, with the preferred means of transport: options and indicative duration, door to door when it matters (for example a ferry plus a drive). Say it is indicative.
3. **Cost level**: low, medium or high compared with the budget, from general knowledge, and say it is indicative. Never search for prices or offers and never give prices: triply does not do it in this version.
4. **First notice on documents**, for each traveller, from the documents in the trip file: whether an identity card is enough or a passport is needed, whether a passport expires too close to the end of the trip, whether a visa or a travel authorization is likely. It is only a first notice: say that phase 3 checks it with official sources. When you are not sure, say so.
5. **Why it fits** and **pros and cons**, thinking of these travellers: ages, pace, interests, what they avoid.

## 3. Present and save

1. Save the proposals **before** asking: one entry in `options` per card — `id`, `"kind": "destination"`, `title`, `summary` (with the climate figures and whether they are verified or estimated), `pros`, `cons`, `"chosen": false`. Run `check`. This way a new session knows what was proposed.
2. Show the cards in one message, five to seven lines each, then one line comparing them. Ask the user to choose; they can also ask for other proposals, propose their own, or mix (for example "the sea of the first one, but closer").
3. When the user asks for other proposals, add the new ones; the earlier ones stay with `"chosen": false`, and the reason they were set aside goes to `progress.log` when the user gave one.

## 4. When the user chooses

1. In `options`: `"chosen": true` on the chosen destination. A destination decided in phase 1 already has it.
2. In `places`: the destination, with the coordinates of the representative place — `{"name", "kind": "city" or "area", "lat", "lon", "country"}`.
3. In `weather`: one entry for the destination and the trip's period — `place` (its id), `start` and `end` (the trip's dates, or the window), `"kind": "climate"`, `temp_min_c`, `temp_max_c`, `precipitation_mm`, `rain_days`, a short `summary`, and the `source` given by `climate`. Only when the figures are verified: an estimate goes only in the summary of the option.
4. In `progress`: a log entry with the choice and its reason; close the open point on the destination; add an open point for each document notice, with `"phase": "entry_requirements"`; `phase` → `entry_requirements`; `next_step`.
5. Run `check` and fix every error.
6. **Folder name.** When the title of the trip is a period ("Agosto 2027"), propose to rename it after the destination ("Sardegna 2027"). Rename only after the user's yes, with `rename-trip`; say that the files already in the folder move with it, untouched. Do not propose it when the title already names the place.

## 5. Close the phase

Tell the user, in a few lines: the destination chosen and why, the climate of the period, how they will get there, the notices on documents, the open points, and the next step: the check of the entry requirements. Then propose to go on with phase 3: `guide entry-requirements`.
