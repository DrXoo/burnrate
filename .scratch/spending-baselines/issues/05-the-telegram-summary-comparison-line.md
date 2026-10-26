# 05: The Telegram summary's comparison line

**What to build:** The Telegram `/summary` carries the same comparison the dashboard
shows, so the two interfaces never disagree about what is normal for the owner, and
omits it entirely when there is no baseline rather than printing an empty line.

**Blocked by:** 04.

**Status:** done

- [x] `/summary` reports the month's spending against its baseline, with the number of months it rests on
- [x] The line is omitted when there is not enough history, rather than rendered with nothing in it
- [x] The verdict is read off the status in the payload and worded as the dashboard words it; the formatter derives no band of its own
- [x] A month that has not started keeps the existing suppression of progress lines and gains no comparison
- [x] Tested at the formatter seam only, dict in and string out


## Comments

**Done.** 6 new tests at the formatter seam and nowhere else; 460 backend pass. The
thinnest ticket of the six, as expected, and the only one that touched a single file
of production code.

Red first: four of the six tests failed on arrival. The two omission tests passed
vacuously, because nothing was rendered yet, and the mutation that removes the status
guard now kills exactly those two -- so they have teeth they did not have at red.

### The discriminating test

`test_format_summary_reads_the_verdict_off_the_status_not_off_the_figures` hands the
formatter a **deliberately inconsistent payload**: 295.00 against 580.00 is half,
which any band derived locally would call well below, while the status says
`in_line`. The status has to win.

That is not a contrived case. It is the defect Phase 8 paid for twice -- a client
that re-derived a budget threshold flipped an on-plan month to a warning around day
26, and this same formatter used to work out a month's tense from a clock of its own
until ticket 17. The mutation that derives the band from `deviation_percent` kills
this test and the anomalous-month test together.

### A deliberate asymmetry with the dashboard

The dashboard **states** that there is not enough history; the bot **omits** the
line. Both are in their tickets and they disagree on purpose: a screen the owner is
looking at makes an absent line ambiguous, and silence there reads as "nothing to say
about your spending", whereas a chat reply is a list of facts and a fact that is not
known is simply not among them. Recorded in `architecture.md` beside the other place
these two clients deliberately differ.

### Decisions taken here

* **The wording is duplicated across the two clients, and that is the right trade.**
  The *verdict* comes from the backend so the two cannot disagree about it; the
  *words* are per-client, in Python here and in `lib/format.ts` there. Phase 8 made
  the same call for the tense suffixes. Sharing the strings would mean shipping them
  through the payload, which is a bigger coupling than two small phrase tables.
* **The comparison sits under the existing unbudgeted disclosure**, reusing the
  `   ↳` continuation idiom rather than introducing a block of its own, and the
  existing line keeps its place.
* **The month count is in the line, not just available.** Two months is few enough
  that the owner should be told, and the bot has no room for a separate caption the
  way the Categories panel does.

### Mutations run

| Mutation | Result |
|---|---|
| Status guard removed | both omission tests, exactly |
| Band derived from the figures | the status test and the anomalous test |
| Uncomparable line always printed | its own test |
