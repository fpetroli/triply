# Phase 0 — first setup

Done once. It creates the **trips folder** and the **user profile**: the data valid for every trip, so that triply never asks them again.

## 1. One grouped message

Say in one sentence that this is the first time and that triply needs a few things once. Then ask everything below in a single message, with a default for each point. Do not ask the language: it is the language of the conversation.

1. **Where to keep the trips.** Propose a folder named "Trips" in the user's language (Viaggi, Voyages, Reisen, Viajes…) **inside the current folder**: there you can work without asking the user for permissions at every change. Show the full path in plain words.

   Say that inside it each trip will have its own folder, with the documents for the user at the top and the files for triply in a hidden `.triply` folder. If the user already has a folder for their trips, or prefers another place, use that one; when it is outside the current folder, say that next time it is better to open Claude directly in that folder.
2. **Who usually travels**, the user included: for each person a name or a label, and the age group (infant under 2, child 2–11, teen 12–17, adult, senior 65+).
3. **Citizenship and documents** of each person: citizenship; passport and/or identity card with their **expiry date only**. Say explicitly that numbers are not needed and will never be stored. This can be skipped and given later.
4. **Usual departure**: city or airport.
5. **How they like to travel**: pace (relaxed, moderate, intense), interests, things to avoid, preferred means of transport. Any of it can be skipped.
6. **Currency** for budgets: propose the one of the user's country.
7. **Map service**, used later to check places, opening hours and travel times. Explain it simply:
   - **OpenStreetMap** — free, no account. The default.
   - **Mapbox** — free account; more precise travel times.
   - **Google Maps** — free monthly quota, but activating it requires a credit card.

   If the user chooses Mapbox or Google, say that the access key will be asked only when the check of the places is available; there is nothing to do now. Never ask for a key in this phase, and never write a key in the profile.

## 2. Create

1. Run `init` with the chosen folder.
2. Write `<trips folder>/.triply/profile.json` with the answers. Example:

   ```json
   {
     "schema_version": 1,
     "language": "it",
     "map_provider": "osm",
     "currency": "EUR",
     "home": {"name": "Milano"},
     "travellers": [
       {
         "id": "anna",
         "label": "Anna",
         "age_group": "adult",
         "citizenships": ["IT"],
         "documents": [{"type": "passport", "country": "IT", "expires": "2030-01-15"}],
         "pace": "moderate",
         "interests": ["arte", "cucina"]
       }
     ],
     "preferences": {
       "pace": "moderate",
       "interests": ["arte", "cucina"],
       "avoid": ["lunghi viaggi in auto"],
       "transport_preferences": ["train"]
     }
   }
   ```

   Leave out what the user skipped (except `travellers`, which needs at least the user). Rules for values: `guide trip-file`.
3. Run `check` on the trips folder and fix any error before going on.

## 3. Close the phase

Tell the user, in a few lines: where the trips folder is, what was saved about them (people, documents with expiry, preferences, map service), and that they can change any of it at any time just by saying so. If a document expires within a year, mention it.

Then, if the user already asked for a trip, propose to start it: phase 1, `guide brief`.
