# Phase 9 — the documents

The documents for the user live at the top of the trip folder, in the trip's language. `check` writes them every time the trip file is valid and has its days, so they are always up to date: from phase 5 they are a draft, marked as such until the verification is done.

| File (in Italian) | What it is |
|---|---|
| `Itinerario.html` | The itinerary to open in the browser: the trip at a glance with the map of the bases, then day by day with times, moves, backups, weather, a map for each day; stays and moves, deadlines, documents and entry, weather, packing, budget, open points, sources |
| `Itinerario.md` | The same itinerary as text, readable in any editor or note app |
| `Scadenze.ics` | A calendar to import: every open deadline with two reminders (a week before and the day before, at 9), the stays and the moves between bases |
| `Bagaglio.md` | The packing list with checkboxes |

The names follow the trip's language (in English: `Itinerary`, `Calendar`, `Packing`).

## 1. Write them

Run `check`. In its answer, `documents` says what was written.

- **`missing_labels`**: the trip's language has no built-in labels. Translate the English labels given (`english`) into the trip's language — the same keys, the `{placeholders}` unchanged, `weekdays` (7, from Monday) and `months` (12) as short forms — and write them as JSON in the file given (`file`) with your file tools. Run `check` again. Do it once: the file stays with the trip.
- **`skipped`**: a file of the user has the same name as a document. It is never overwritten: tell the user, and propose to rename their file.
- **`ticks_read`**: the user ticked or added items in the packing list file; they are now in the trip file.

## 2. Show them

Tell the user, in a few lines, what each file is and how to use it:

- `Itinerario.html`: open it with a double click; the maps need an internet connection, the rest works without; it prints well (maps are left out);
- `Scadenze.ics`: import it into their calendar (Google, Apple, Outlook), best into a **new calendar named after the trip**: when the deadlines change, they can delete that calendar and import the file again, with no duplicates;
- `Bagaglio.md`: they can tick the boxes in any editor or note app, or tell you in the chat; lines they add with a checkbox become items of the list;
- the documents are rewritten after every change: changes made by hand to the itinerary are lost (ticks in the packing list are kept). To change the trip, they ask you.

## 3. Close the phase

- `progress.log`: the documents created;
- `progress.phase` stays `documents`; `next_step`: what is still to do (bookings, forecast, packing), or that the trip is ready;
- run `check`.

From now on, after a change, say once in the conversation that the documents are updated; not after every change.
