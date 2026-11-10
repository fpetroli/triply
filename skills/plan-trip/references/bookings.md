# Phase 7 — bookings and deadlines

It turns the trip into a list of **what to book and by when**, with links that open the booking sites with places, dates and travellers already filled in. Then, at any time, it records what the user has booked and what they spent.

triply never queries the booking sites, never sees prices and never books: the user books. The links carry no affiliate code.

## 1. What to book

Read the trip file. What may need a booking:

- the **stays** and the **transports** with `booking.status` `to_book`;
- the **stops of the days** that need a ticket or a table in advance: timed entries, limited-entry places, shows, famous restaurants (look at the notes and at the verification of phase 6). Give each one `"booking": {"status": "to_book"}` on the stop;
- what needs no booking in advance (a regional train, a free museum): `"status": "not_needed"`.

Add the **official site** where to book, when you know it (from phase 6, or the site of the place or the operator), to `booking.links` as `{"label": "<name of the site>", "url": "…"}`. For flights, add the IATA code (`iata`) of the two places when you are sure of it: the code of the city when it has several airports (for example TYO, OSA, MIL), otherwise the airport.

Then run `links "<trip folder>"`: it adds to every stay and transport still to book the search links already filled in (Booking.com and Airbnb for the stays; Google Flights and Skyscanner for the flights; Rome2rio for trains, buses and ferries), keeping the links you added. Run `check`.

## 2. By when

Give each thing to book one deadline in `deadlines`: `{"id", "title", "due", "kind": "booking", "related": "<id of the stay or transport, or of the place of the stop>", "reason", "done": false}`, with `source` when the date comes from the web. When a deadline for the same thing exists already, update it instead of adding another.

The dates:

- **stays**: in high season, on holidays or big events, or where there are few places to stay: within two weeks; otherwise two or three months before the check-in. Suggest a rate with free cancellation;
- **long-haul flights**: three or four months before; **short and medium-haul**: one or two months before;
- **trains and ferries with reservation**: from the day sales open, which you read on the official site of the operator and on another source, as in phase 6; ferries in peak season, one or two months before;
- **limited-entry places and shows**: from the day tickets are released, read on the official site and confirmed by another source;
- **restaurants**: as their site says, otherwise two to four weeks before.

A deadline is never in the past: when the right moment has passed, set it for today and say it is urgent. It is never after the start of the trip.

## 3. Show the list

Show the deadlines in order of date, grouped (for example: this week, within a month, later). For each one: what, by when, why in a few words, and the links by name, as Markdown links. Then:

- the links open the search already filled in; if a site has changed its format, the link opens the site without the data;
- for flights there and back, a return ticket or a multi-city search on the same site often costs less than two one-way tickets;
- the document deadlines of phase 3 are in the same list.

Ask for changes. **Stop.**

## 4. Close the phase

When the user agrees:

- `progress.log`: the choices with a reason (for example a stay to book at once because of a holiday);
- `progress.phase` → `weather_packing`; `next_step`;
- run `check` and fix every warning about the deadlines.

Tell the user that from now on, at any time, they can simply tell you what they have booked ("ho prenotato l'hotel a Kyoto, 480 euro, cancellazione gratuita fino al 1° marzo") and triply keeps the list and the budget up to date.

## 5. When the user has booked something

This works in any phase. From what the user says:

- the booking: `status` `booked`; `cost` `{"amount", "currency"}` when they give it; `reference` when they give it; for a stay, the name of the accommodation in `name`; for a transport, `depart_time` and `arrive_time` when they give them, with the `duration_min` that follows and `duration_source` `{"provider": "user", "checked_at": "<today>"}`;
- its booking deadline: `done: true`;
- **new dates from the booking**: free cancellation until a date → a deadline with `kind` `cancellation` ("last day to cancel for free: …"); a balance to pay → a deadline with `kind` `payment`; both with `related`;
- a cost with no booking (insurance, a pass bought online): a line in `budget` with `status` `confirmed`; the costs of the bookings go only in their `cost`, never also in `budget`;
- never card numbers, passwords or document numbers: if the user gives them, do not write them and say that triply does not need them.

Run `check`, then `costs "<trip folder>"`: tell the user in one line how much is committed and how much of the budget is left, and plainly when the budget is exceeded. When every stay and every transport is `booked` or `not_needed`, set `trip.status` to `booked` and say so.
