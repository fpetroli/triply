# Phase 8 — weather and packing

It gives the weather of each base for its dates, then a packing list built from the weather, the activities of the days and the documents, with a reason for each item that is not obvious.

## 1. The weather

For each stay, take its place and its nights (from `check_in` to the day before `check_out`):

- **more than 15 days before those dates**: the typical weather, `climate --lat <lat> --lon <lon> --from MM-DD --to MM-DD`, averaged over the last years;
- **within 15 days**: the forecast, `forecast --lat <lat> --lon <lon> --from YYYY-MM-DD --to YYYY-MM-DD`; where it stops (`available_until`), the typical weather covers the rest.

Add a place with a different weather when a day trip goes there: mountains, a much higher town, the sea in another season (for example a day on a volcano, or a mountain pass).

Save one entry per stay (and per such place) in `weather`, replacing the older entries for the same place and dates: `{"place", "start", "end", "kind": "climate" | "forecast", "summary", "temp_min_c", "temp_max_c", "precipitation_mm", "rain_days" (climate), "rain_probability_pct" (forecast: the highest of the period), "source"}`. For a forecast, `temp_min_c` and `temp_max_c` are the lowest minimum and the highest maximum of the period; the `summary` tells the days that stand out ("rain on the 11th and 12th"). Run `check`.

Tell the user in a few lines, base by base: temperatures, rain, and what it means (a jacket in the evening, an umbrella on most days). With a forecast, look at the days of the program: a rainy day with an outdoor main activity is a problem to solve with the backup of that day, as in phase 6.

## 2. Two questions

In one message, with a default for each:

- the luggage: hand luggage only, or also a checked bag (default: checked bag)? With hand luggage only, liquids go in containers of at most 100 ml in a clear bag, and the quantities are smaller;
- anything personal that must not be forgotten: medicines, glasses or lenses, a child's things, devices (default: nothing more). Write them in the list, never in the profile: medicines and health data stay in this trip only.

## 3. The packing list

One list for the trip, in `packing`: `{"item", "category", "reason", "quantity", "traveller", "packed": false}`. Shared items appear once (the adapter, the sun cream); what belongs to one traveller has `traveller`; clothes have the quantity for everyone together. The categories are `documents`, `clothing`, `health`, `electronics`, `toiletries`, `gear`, `other`.

What goes in, with its reason when it is not obvious:

- **documents**: the documents of each traveller from the trip file (passport, identity card, driving licence and the international permit when they drive abroad and it is required), the visas and authorizations of phase 3, the booking confirmations, the travel insurance, the means of payment and the local currency;
- **clothing**: from the weather of every base (layers when mornings are cold, light clothes for the heat, rain jacket or umbrella when it rains often), from the activities (comfortable shoes for long walks, socks for places where you take off your shoes, shoulders and knees covered for religious places, swimsuit for the sea or hot springs, something smart for a formal dinner). For trips longer than about a week, clothes for a week and a wash on the way;
- **health**: the medicines the user said, a small first-aid kit, sun cream when it is sunny, insect repellent where it is needed; the health requirements of phase 3 (vaccination certificate);
- **electronics**: the plug adapter for the sockets of each country of the trip, and a note when the voltage differs; read the socket types on the site of the IEC (World Plugs) or of the national authority, with another source, and save the `source` on the item; chargers, a power bank;
- **toiletries**: as needed, with the 100 ml rule for hand luggage only;
- **gear**: what the activities need (a day backpack, a bottle, a torch for caves, binoculars).

No obvious filler: what everyone takes anyway (underwear, a toothbrush) is one line per category at most. Run `check`.

Show the list grouped by category, compact: one line per item, with the quantity and, in brackets, the reason or the traveller when there is one. Ask for changes. **Stop.**

## 4. Close the phase

When the user agrees:

- `progress.log`: the choices that matter (hand luggage only, a wash on the way);
- `progress.phase` → `documents`; `next_step`;
- run `check`.

Tell the user: the weather in two lines, how many items are on the list, that they can tell you what they have packed ("ho messo in valigia i documenti") and you tick it off, and that the forecast will be offered when the trip is reopened in the last 15 days before departure.

## 5. Later: the forecast and the ticks

- When the trip is reopened in the **last 15 days before departure**, or `check` says the forecast is available or old, offer to update the weather with the forecast (section 1), and once more two or three days before leaving. When the forecast changes what to pack (rain, cold, heat), update the list and say what changed.
- When the user says they have packed something, set `packed: true` on those items and say how many are left.
