# Phase 3 — entry requirements

It checks, for every traveller and every country of the trip, what is needed to enter it, with official sources and the date of the check. When something is missing it stops and tells the user what to do and by when.

## 1. What you need first

Read the trip file: travellers (citizenships, documents with their expiry), the chosen destination and its countries, the dates, the means of transport, the open points of phase `entry_requirements`.

Ask, in one grouped message, only what is missing:

- the **citizenship** of a traveller, when it is not in the file;
- the **documents** each traveller has (type, issuing country, expiry; never a number), when the file has none;
- the **stopovers**, when the trip is by air and the user already knows them (otherwise: check them again when the flights are chosen — add an open point);
- for a **minor**: whether they travel with both parents, one parent or other adults;
- whether a **car** will be rented or driven abroad, when it is not clear.

## 2. What to check

For each traveller and each country — the destination countries and the stopover countries:

| `kind` | What to check |
|---|---|
| `document` | Whether an identity card is enough or a passport is needed; the validity required (for example "6 months beyond the date of departure from the country", blank pages); compare it with the document's expiry and the trip's dates, counting the months exactly |
| `visa` | Visa, electronic travel authorization (ESTA, eTA, ETIAS, K-ETA and similar) or registration on arrival; how long it takes to get, how long it lasts, where to apply |
| `transit` | Whether a stopover needs a transit visa or authorization, also without leaving the airport |
| `minors` | Documents of a minor; declarations or consents when a minor travels without one or both parents |
| `health` | Mandatory vaccinations or certificates (`mandatory: true`); the recommended ones go in one entry with `mandatory: false` |
| `driving` | Whether the driving licence is accepted or an international driving permit is needed |
| `other` | Anything else the official sources require (for example insurance, proof of return, funds) |

Skip what does not apply (no `driving` without a car, no `minors` without minors). A trip inside the traveller's own country needs only one `document` entry.

## 3. Official sources only

Use web search and web fetch to read the official pages. A source is official only when it is one of these:

1. **The foreign ministry of the traveller's country of citizenship**, on its travel advice pages — for example Italy `viaggiaresicuri.it`, United Kingdom `gov.uk/foreign-travel-advice`, United States `travel.state.gov`, Germany `auswaertiges-amt.de`, France `diplomatie.gouv.fr`. Their country pages also cover health and driving.
2. **The government of the destination country**: its immigration authority, its official visa or authorization portal, its embassy or consulate in the traveller's country.
3. **For the Schengen area and the European Union**, the official sites of the EU (`europa.eu`, for example `travel-europe.europa.eu` for ETIAS and the Entry/Exit System).

Never use blogs, travel agencies, forums or visa services as sources. Beware of look-alike sites that sell authorizations (for example ESTA or ETIAS) at a higher price: give the user only the government's own portal, and say so when it matters.

When two official sources disagree, show both to the user and follow the stricter one; note the other one, with its link, in `notes`.

Some official sites cannot be read automatically: a page comes back empty (it needs a browser to show its content) or refuses the request. Then:

1. Try the other official sources of the list, and other pages of the same authority (for example its English version, or the immigration authority instead of the embassy). Use web search limited to official domains to find them.
2. Never try to get around a site that refuses automatic reading, and never take the text of search results as the content of a page: a search result only tells you where to look.
3. What stays unverified: do not guess. Write it with `"status": "unknown"`, put the official page to check in `check_url`, and tell the user what you think is likely, saying plainly that it is not verified.

The same applies when web search or web fetch is not available, or the user does not allow it.

**Check by hand.** Give the user a short list: for each link, what to look for ("whether Italians need a visa for tourism, and for how long"). Ask them to tell you what they read, or to paste the text. Record it with `"provider": "user"`, the `url` of the page they read and today's date; when what they report is incomplete or unclear, say what is still missing.

## 4. Save

One entry in `entry_requirements` per traveller, country and requirement:

```json
{"country": "JP", "traveller": "giulia", "kind": "document", "requirement": "Passport valid for the whole stay",
 "status": "action_needed", "notes": "Giulia has only an identity card: she needs a passport before departure.",
 "source": {"provider": "web", "url": "https://www.viaggiaresicuri.it/", "title": "Viaggiare Sicuri — Giappone", "checked_at": "2026-11-08"}}
```

- `status`: `ok` when the traveller already meets it, `action_needed` when they must do something, `unknown` when it could not be verified.
- `source` is required for `ok` and `action_needed`: the page actually read, its title, today's date.
- For every `action_needed` with a time limit, add a deadline in `deadlines`: `{"id", "title", "due", "kind": "document", "reason", "related": "<traveller id>", "search_url": "<official page where to apply>", "done": false}`. Choose `due` with a margin: the official processing time, plus some weeks for a passport. When the dates are a window, count from `window_start`.
- Add one more deadline, **check the entry requirements again**, about 30 days before departure, `kind` `document`, with reason "requirements change".
- Close the open points of phase `entry_requirements` that are resolved, recording the outcome in the log; add an open point for what is still `unknown`.

Run `check` and fix every error.

## 5. Tell the user and stop

Tell the user, per traveller, in a few lines:

- what is fine;
- **what they must do**, by when, and where (the official link), first and clearly;
- what could not be verified, with the links to check by hand;
- that requirements change: triply will check them again about a month before departure, and you can ask to check them again at any time.

When something is `action_needed` or `unknown`, ask whether to go on with the route anyway; continue only with the user's yes. Then:

- `progress.log`: what was found and, when the user chose to go on with something still to do, that choice;
- `progress.phase` → `route`; `next_step`;
- run `check`.

Then propose to go on with phase 4, the route and the bases: `guide route`.

## Checking again

When the user asks to check again, or a check is more than three months old (`check` warns about it), repeat sections 2 to 4 for the entries concerned: update `status`, `source.checked_at` and the deadlines, and say what changed. When the travellers, the destination, the dates or the stopovers change, check again the entries they touch.
