# Security Policy

## Reporting a Vulnerability

Please report security vulnerabilities privately, not as a public GitHub
issue.

**Preferred: GitHub Security Advisories** — use this repository's
["Report a vulnerability"](https://github.com/jpziller/DataMigration/security/advisories/new)
feature (Security tab → Advisories → Report a vulnerability). This opens a
private channel with the maintainer so a fix can land before public
disclosure.

This project doesn't use versioned releases — security fixes are applied
directly to `main`.

## Scope

This is a CLI tool, run locally by an already-credentialed operator,
against their own SQL Server instance and Salesforce org — see
[`docs/SECURITY_OVERVIEW.md`](docs/SECURITY_OVERVIEW.md) for the full
trust-boundary breakdown (credential inventory, what's code-enforced vs.
convention-enforced, optional external hops). Vulnerabilities of interest:

- Credential handling (`.env`, access tokens, connection strings) being
  read, logged, or transmitted somewhere it shouldn't be.
- SQL injection or command injection in any code path.
- A generated artifact (mapping doc, solution doc, migration run book,
  etc.) leaking a credential or secret into its output.
- Any gap between what `docs/SECURITY_OVERVIEW.md` claims and what the
  code actually does.

Out of scope: vulnerabilities in Salesforce itself, SQL Server itself, or
third-party dependencies (report those upstream) — though a dependency
pinned here at a known-vulnerable version is fair game to flag.

## Response

This is a solo-maintained project — best-effort response, no formal SLA.
Confirmed vulnerabilities get a fix and a note in the commit message;
credit given if you'd like it.
