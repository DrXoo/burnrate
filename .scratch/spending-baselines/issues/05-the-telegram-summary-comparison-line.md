# 05: The Telegram summary's comparison line

**What to build:** The Telegram `/summary` carries the same comparison the dashboard
shows, so the two interfaces never disagree about what is normal for the owner, and
omits it entirely when there is no baseline rather than printing an empty line.

**Blocked by:** 04.

**Status:** ready-for-agent

- [ ] `/summary` reports the month's spending against its baseline, with the number of months it rests on
- [ ] The line is omitted when there is not enough history, rather than rendered with nothing in it
- [ ] The verdict is read off the status in the payload and worded as the dashboard words it; the formatter derives no band of its own
- [ ] A month that has not started keeps the existing suppression of progress lines and gains no comparison
- [ ] Tested at the formatter seam only, dict in and string out
