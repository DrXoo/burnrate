# 02: A category's spend shown against its own baseline

**What to build:** On the Categories page, each category row shows its spend for the
month on screen beside what that category normally costs the owner, with a verdict —
or states plainly that it has no baseline. This is the tracer bullet for the whole
feature: it carries the Qualifying Month rules, the baseline arithmetic, the bands,
and the first interface, end to end.

It comes first because the aggregate comparison in ticket 04 is *defined* in terms of
which categories have a baseline, so it cannot be built before this.

**Blocked by:** 01.

**Status:** done

- [x] A category with spend in at least the presence floor's number of Qualifying Months shows its spend beside its baseline and the deviation as a percentage
- [x] A category below the presence floor shows no baseline and says so; no monthly figure is invented for a category the owner spent in once
- [x] A month whose unclassified outgoing amount exceeds the coverage floor is not a Qualifying Month, and coverage is measured **by amount**: a month with few unclassified rows carrying most of its money is excluded, while a month with many unclassified rows carrying very little is admitted
- [x] The current month is never a Qualifying Month for its own baseline
- [x] Below the minimum Qualifying Month count the baseline status says so and no baseline is shown anywhere
- [x] The baseline divides by the Qualifying Months the window reaches, not by the months the category happened to appear in
- [x] For the current month, each Qualifying Month contributes only spend up to the same day of the month, clamped to that month's last day, so a part-month is never measured against a whole one
- [x] A closed month is compared whole against whole
- [x] A month that has not started makes no comparison
- [x] One status names the whole judgement across its five states; the page renders words and computes no band and no percentage the payload does not state
- [x] An anomaly is raised only when spend is at or above the baseline times the anomaly ratio; spend below the baseline reports the deviation and raises nothing
- [x] The number of Qualifying Months the baseline rests on is in the payload and on screen
- [x] Archived Categories are absent from the comparison list
- [x] Ignored transactions count toward neither the month's figure nor any baseline
- [x] Transfers count toward neither, by the existing category-type restriction
- [x] The per-category list includes a category with spend and no active budget, which the existing budget-usage list would omit
- [x] The baseline window is read from settings with a default of three months
- [x] Every pre-existing summary field is unchanged, asserted as a regression
- [x] No migration, no new table, and nothing stored: every figure is recomputed from transactions on each request
- [x] Tests live only at the pure-domain seam, the summary service seam, and page rendering. Nothing is tested elsewhere
- [x] Fixtures include a month shaped like the owner's June — a few unclassified rows carrying most of the money — and a month of the inverse shape, so that a row-based coverage measure cannot pass both
- [x] Every fixture pins "today" through the injectable clock; no fixture reads the real date
- [x] Each of these mutations puts something red: measuring coverage by row count; dividing by months present; dropping the presence floor; admitting the current month as a Qualifying Month; comparing the current month against whole past months; firing the anomaly downward


## Comments

**Done.** 62 new backend tests and 6 new page tests; 425 backend and 52 web pass.
New: a pure-domain baseline policy module, a `BaselineService` owning the queries
that read other months, three fields on the summary response including a
per-category comparison list, a `BASELINE_WINDOW_MONTHS` setting, and a comparison
line on each Categories row. No migration, no new table, nothing stored.

### Where the loop held and where it did not

Red first on nine cycles: the trailing mean, the presence floor, coverage, the
minimum-months status, the comparison bands, the end-to-end tracer bullet, the
not-started month, the window setting, and the whole page.

**Eight tests went green on arrival**, because the tracer bullet's implementation
already covered the ground they described. Each was mutation-checked instead, per
`AGENTS.md`, and every mutation is listed below with the value it produced. The
honest reading is that after cycle 7 this stopped being red-green for the service
seam and became write-then-prove; naming that is better than implying otherwise.

### The mutation that survived, and what it found

**The minimum-months rule was not tested at all**, and three review passes by
reading would not have found it. `test_one_qualifying_month_is_not_enough_to_claim_anything`
looked like it covered the rule. Disabling the rule entirely changed nothing: with
one Qualifying Month a category can have spend in at most one of them, so the
*presence floor* already refused the baseline. The two rules masked each other and
the test passed for the wrong reason.

They are separate constants so either can move, and the fix is to isolate them —
lowering the presence floor to one makes September alone clear it, leaving the
minimum-months rule as the only thing standing between the owner and a "baseline"
that is last month wearing a word that implies more. With that test in place the
same mutation fails on `'300.00' is None`.

This is the second time this ticket that a defect was only reachable by running
something: the first was ticket 01's double-escaped newline.

### The fixture that had to be designed rather than written

The rows-versus-amount defect is **unfalsifiable at the domain seam** —
`month_qualifies` takes amounts, so its signature already encodes the decision.
Only the query can get it wrong, so the service fixture is the whole defence, and
the obvious version of it does not work: two months of opposite shape produce the
same *count* of qualifying months under either measure, so `baseline_months_count`
cannot tell them apart.

What discriminates is which months qualify. Three months — July clean, August
hiding 905 of its 1000 in one unfiled row among twenty, September with ten unfiled
rows of 2.00 beside one charge of 600 — give both measures two qualifying months
and different baselines: 450 by money, 197.50 by rows. Under the row mutation the
two count assertions still pass and only the baseline assertion fails, which is
the proof the design was necessary.

### Decisions taken here that the ticket did not specify

* **`BaselineStatus` has a third value, `month_not_started`.** A future month has no
  outcome to compare however much history sits behind it, and the alternatives were
  worse: reporting `insufficient_history` lies about the reason, and an empty list
  with `ok` reads as "nothing spent anywhere". Each client cross-referencing
  `safe_to_spend_status` to find out whether a comparison exists is the
  re-derivation ADR-0002's amendment exists to stop. Same trade Phase 8 re-decided
  when it split `not_current_month` in two.
* **A month with no outgoing money at all does not qualify.** Nothing in it is
  unclassified, so a share-based test admits it and it then contributes a zero to
  every baseline. Refused on the weakest available evidence; ticket 03 owns the
  real version of this.
* **The comparison carries its own spend figure**, which can differ from the
  month's headline for the current month, because both sides are measured to the
  same day. A standing order due later in the month counts toward monthly spending
  and not toward the comparison. Stated in the schema and the type rather than
  reconciled away: they answer different questions.
* **`MonthTense` is taken, not derived.** It already exists and the summary service
  already establishes it, so `BaselineService` receives it. That also removed a
  duplicate computation in `get_summary`.
* **The month-count caption is published once, not per row.** The divisor is the
  same Qualifying Months for every category, so repeating it per row would be noise.

### Mutations run, with the value each produced

| Mutation | Result |
|---|---|
| Coverage measured by row count | `197.50` vs `450.00` |
| Divisor over months present | `450.00` vs `300.00` |
| Presence floor dropped | 4 domain examples |
| Month on screen in its own window | `500.00` vs `300.00`, 4 tests |
| Current month against whole past months | `550.00` vs `100.00` |
| Cutoff not clamped to month length | `250.00` vs `200.00` |
| Anomaly fired downward too | 2 band examples, the live Food case among them |
| `in_line` tolerance 15% → 5% | 2 band examples |
| Coverage floor 5% → 70% | 3 coverage examples |
| Archived categories not excluded | its own test |
| Transfers not excluded | its own test |
| Ignored rows not excluded | its own test |
| Deviation unsigned | 3 examples |
| Deviation as a ratio | 6 examples |
| Dependency drops the window setting | its own test |
| Page does not withhold the comparison | its own test |
| Minimum-months guard disabled | **survived**, then fixed; now `'300.00' is None` |

### For the tickets that follow

* **Ticket 03** inherits a working `_month_qualifies` with one of its two tests in
  place. The zero-outgoing refusal is a placeholder for its job, not a substitute.
* **Ticket 04** gets `category_baselines` as the input to the Comparable /
  Uncomparable split: a row with a null `baseline_amount` is exactly what falls into
  the disclosed bucket.
* **Ticket 06** should expect more than 6 statements now — the comparison reads one
  month window per month in the window, plus two coverage queries per candidate
  month and one for names. The current month should finally cost more than a closed
  one.
* The page tests needed one markup change: `renderToStaticMarkup` splits a number
  into its own `<span>`, so a phrase assembled around `<span className="num">{n}</span>`
  is not contiguous in the output. The fix was to make the phrase one text node,
  which is also what the owner actually reads.
