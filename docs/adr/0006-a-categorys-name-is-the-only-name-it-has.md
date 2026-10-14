# A category's name is the only name it has

The name on a budget row was never a budget field: `BudgetService` reads
`Category.name` through its join and reports it as `category_name`, and the same
name labels rules, the dashboard's per-category usage and the Telegram summary.
Nothing could change it — `/categories` had only `GET` and `POST` — so every one
of those labels was fixed for the life of the category. `PATCH /categories/{id}`
now renames the category, and because all four surfaces read the name through a
join rather than holding a copy, one rename reaches all of them.

The alternative a reader is most likely to reach for is a display label on the
budget itself, which is why it is recorded as rejected below.

## Considered Options

**A `name` column on `budgets`**, overriding the category's name on the budgets
page. Rejected: budgets are already one-per-category-per-month, so the label
would duplicate the category's name in the common case and diverge from it in
the rest. The dashboard's budget usage, the rules list and the Categories page
all group by category and would keep showing the old name, so the owner would
see "Rent" in one place and "Housing" in another for the same money. Two names
for one thing is also two things to keep in step on every later read.

**Renaming through a per-surface setting** was not seriously considered, but has
the same defect multiplied.

## Consequences

**Uniqueness is enforced case-insensitively by the application, which is
stricter than the database's exact `UNIQUE` on `name`.** The check excludes the
row being renamed, which is what lets a category be re-cased in place: `Food` to
`food` matches the uniqueness query, but the row it matches is the one being
renamed. Creating and renaming share that one check, so they cannot disagree
about what counts as taken.

**A name already in use answers `409`, not `400`.** The owner picking a name
that exists is a conflict to resolve, not a malformed request, and the web UI
keeps its editor open on the reason rather than discarding it. The conflict is
carried as a typed exception rather than recognised by its wording, so the status
does not depend on the phrasing of a sentence written for the owner. Creating a
category answers `409` for the same clash, from the same exception.

**Nothing stores a copy of a category's name**, and nothing should start. A
denormalised copy anywhere — a cached label on a budget, a name written into a
transaction row at import — reintroduces exactly the divergence this rejects.
