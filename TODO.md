# Djaq TODO

Consolidated backlog. Status as of the IR rewrite + write-side work (June 2026).
The conformance harness (`./manage.py test`, run with `DJAQ_DB=sqlite|postgres`)
guards everything; keep it green.

## Bugs / correctness

- [x] **Relation aliasing.** ~~Two relations to the same target collapse into one
      join; self-referential FKs impossible.~~ FIXED: relations keyed by join
      *path*, aliased on table collision, joins represented as `parent` +
      `join_pairs` and emitted via `parent.ref`/`self.ref`. Added `Category`
      self-referential model + tests (`test_dual_fk_relations`,
      `test_self_referential_join`, resolver aliasing tests).
- [ ] **Reverse m2m.** `DjangoSchemaProvider` skips `ManyToManyRel` (the provider
      `continue`s past it). Real apps query reverse m2m.

## Read side

- [ ] **`DjaqResult`** — a DataFrame-like result object with a simpler API than
      pandas, on the streaming foundation. (Secondary thread; see
      `djaq-result-design` memory.)
- [ ] **Phase-3 syntax improvements (opt-in).** Now that the parser is
      hand-written (`frontend.py`), layer in nicer surface syntax (e.g. `=` for
      equality, a first-class `@name` token) without breaking the current grammar.

## Write side (deferred from the lean first cut)

- [ ] Declarative write commands: `Update(entity).where(pred).set(...)` /
      `Delete(...).where(...)` with Djaq predicates + `UPDATE/INSERT/DELETE` SQL
      generation in the generator.
- [ ] Django-free (raw-SQL) write path — also the deliberate signal-free fast path.
- [ ] Write-scoping via `DJAQ_SCOPE` (which entities/fields a caller may mutate).

## Dialects

- [ ] **Verify MySQL dialect against a live server** (Docker `mysql:8` +
      `pip install pymysql` + `install_as_MySQLdb()` shim), then `DJAQ_DB=mysql`
      against the harness and fix any gaps. `generator/mysql.py` is currently
      string-verified only.

## Performance

- [ ] Row materialisation in `executor.py` (the EXEC-side gap vs Django
      `.values()`). Paul has ideas — discuss before implementing.

## Packaging / cleanup

- [ ] Lazy package `__init__` so the pure pipeline imports with Django *absent*
      (not just unconfigured). Optional / low value.
- [ ] Broader ruff cleanup of pre-existing issues in `app_utils`, `djaq_ui`,
      `djaq_api/tests.py` (~45, none in the rewritten query package).
- [ ] Stale `book_list` view in `books/views.py` uses the old inline-model
      syntax (`DQ("(...) Book b")`) and is broken against the current API.

## Test-app realism (decide scope)

- [x] ~~Add a self-referential model (`Category.parent`) + self-join / dual-FK
      tests~~ — done as part of the aliasing fix.
- [ ] Decide in/out of scope, then build the test app toward what's in:
      m2m `through` models with payload fields; multi-table inheritance;
      `GenericForeignKey`/contenttypes; `JSONField`/`ArrayField`; UUID / non-int
      PKs; `DateTimeField`/`DurationField`/`TimeField`.
