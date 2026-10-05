# 01: Resolve civil dates through APP_TIMEZONE

**What to build:** "Today" and "the current month" mean today in the owner's own
timezone rather than UTC. Near midnight the dashboard stops reporting yesterday,
and on the first of the month it stops reporting the whole previous month. The
same latent bug exists in four places, so all four are fixed together.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A setting names an IANA timezone and defaults to UTC, documented in the example environment file
- [ ] The summary resolves today and the current month through that setting
- [ ] Both civil-date call sites in the budget service and the one in the Telegram notifier resolve the same way
- [ ] A test proves that with the timezone set ahead of UTC, a reading taken just after local midnight reports the new local day
- [ ] A test proves the first of the month is not reported as the previous month
- [ ] The architecture doc records the setting
