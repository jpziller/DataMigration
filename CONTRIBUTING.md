# Contributing

Thanks for taking a look at this project. It's primarily a solo-maintained
framework, but issues, ideas, and pull requests are welcome.

## Before you start

- Read [`README.md`](README.md) for what this framework does and how it's
  structured (template vs. generated content).
- Read [`CLAUDE.md`](CLAUDE.md) — the hard rules and conventions this repo
  is built around (SQL-centric design, fingerprint-based result mapping,
  the Email Deliverability attestation, etc.). Changes should follow
  these, not work around them.
- Check [`ROADMAP.md`](ROADMAP.md) first — it tracks what's built, what's
  a deliberately deferred idea, and why. Something already logged there
  (with its reasoning) saves you re-proposing it from scratch; a "not
  built" item is often already scoped enough to just start on.

## Reporting bugs

Open a GitHub issue with:
- What you ran (the CLI command/verb) and what you expected vs. got.
- Whether it touched a live Salesforce org or just the SQL Server mirror
  DB — this changes how urgent/risky the bug is.
- **Never** paste `.env` contents, access tokens, or real org/customer
  data into an issue.

For a security vulnerability specifically, see
[`SECURITY.md`](SECURITY.md) instead — don't file it as a public issue.

## Pull requests

- Keep transformation logic in `sql/transformations/*.sql`, not inlined
  into Python or one-off shell commands.
- Don't invent Salesforce object/field API names — confirm via
  `describe`/`dump-describe` first.
- If you're adding a new credential type, network listener, or auth
  boundary, update `docs/SECURITY_OVERVIEW.md` in the same PR.
- Don't reference by name any commercial tool this framework builds a
  replacement for (see the Licensing section of `CLAUDE.md` for the full
  list and rationale) — describe behavior generically instead.
- Never commit `.env`, `server.key`, real org metadata, or real
  mapping/profiling data — check `.gitignore` covers what you're adding
  before committing.

## Code style

No enforced linter/formatter yet — match the surrounding file's style.
Library modules (e.g. `bulkops.py`, `batch_advisor.py`) return data;
only `cli.py` prints to the console — keep that separation when adding a
new verb.

## License

By contributing, you agree your contribution is licensed under this
project's [MIT License](LICENSE).
