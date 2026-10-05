# 06: Safe to Spend Today, in the domain and the API

**What to build:** The number itself. The owner can ask the API how much they can
spend today without putting the month's Variable Budgets out of reach, and get an
answer that is never negative, that accounts for a Fixed Budget that overshot,
and that carries a status they could read as a colour without reading the number.

The status is judged against On-Plan Remaining rather than the planned daily
pace, because the obvious comparator warns in the last week of every month even
when spend tracks budget exactly.

**Blocked by:** 02, 05

**Status:** ready-for-agent

- [ ] The allowance is remaining Variable Budget, less Fixed Overrun, over the days left in the month counting today
- [ ] The allowance is never negative
- [ ] Fixed Overrun is summed per Fixed Budget category from Booked spend, so an underrun on one cannot fund an overrun on another
- [ ] Status is a single five-value field, and the amount is null for the no-budget and not-current-month cases
- [ ] A zero amount can only mean budgets exist, the month is current, and they are used up
- [ ] A month that is exactly on plan reads on-track on every day of that month, including the last week
- [ ] The last day of the month resolves without a special case, and the zero On-Plan Remaining case is guarded
- [ ] The API exposes the allowance, its status and the Fixed Overrun total
- [ ] Domain tests cover the bands at day 1, 15, 25, 29 and the last day, the zero clamp, and both undefined cases, as worked examples with no database fixture
- [ ] The metric definitions doc matches what was implemented
