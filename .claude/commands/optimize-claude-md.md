---
description: Audit and trim CLAUDE.md per docs/CONTEXT_DOC_STANDARDS.md -- relocate rationale to its home docs and compress the command inventory, losing no knowledge and changing no behavior. Proposes on a branch; a human reviews and merges.
allowed-tools: Read, Grep, Glob, Edit, Bash(git *), Bash(wc *), Bash(.venv/Scripts/python.exe *)
---
Optimize `CLAUDE.md` (or the file named in `$ARGUMENTS`, if given) so it stays
lean and load-bearing. `docs/CONTEXT_DOC_STANDARDS.md` is the **authority** —
this command executes it; it does not restate the rules. Read that file first
and follow its four-class rubric, routing table, and invariants **exactly**.

`$ARGUMENTS` (optional): a `##` section name to scope the pass to, or the word
`measure-only` to report metrics + a proposed classification without editing.
Default: a conservative full-file pass per the standard.

Procedure:

1. **Read the standard** — `docs/CONTEXT_DOC_STANDARDS.md`. It governs
   everything below. If the task and the standard ever seem to conflict, the
   standard wins (or stop and ask).
2. **Baseline** — measure the target: `wc -l -w CLAUDE.md`, and per section
   (`grep -n '^## ' CLAUDE.md`). Compare against the last row of the standard's
   size log to show drift. If `measure-only`, report and stop here.
3. **Branch + restore point** — create a branch (never work on `main`). Because
   this rewrites the operating manual, run `git tag pre-context-trim` first as a
   one-command restore point (git history is the archive; do not make a
   gitignored copy).
4. **Classify** every block as Directive / Rationale / Reference / Stale per the
   rubric.
5. **Relocate** each Rationale (and any Reference back-story): confirm the
   content already lives in its routing-table home (`README.md` / `ROADMAP.md` /
   `postmortems/` / `validators/` / `okf/` / the command's module docstring);
   add it there if it's missing; only then replace the inline block with a
   one-line pointer. **Never delete without landing it somewhere first.**
6. **Compress** each Reference block (command descriptions, flag dumps) to
   name + one-line purpose + key flags + pointer. **Every CLI command must still
   appear** — the inventory stays complete.
7. **Flag Stale** items in place — list them for the human; never auto-delete.
8. **Invariants check** (the standard's five points): every hard rule keeps its
   number + short name; safety-critical rules 1-9 and 12 stay fully explicit
   inline; every command still present; every relocation verified landed in its
   destination; behavior semantics unchanged.
9. **Log** — append a row to the size log in `docs/CONTEXT_DOC_STANDARDS.md`
   (date, trigger, before, after, Δ, notes).
10. **Report + PR** — output before/after metrics (% reduction), a **move
    manifest** (every relocated block → its destination), and the
    **stale-for-decision** list. Open a PR with these in the body. **Do not
    merge** — this is human-owned (like Hard Rule 11); a person reviews the diff
    and the manifest, confirms nothing of substance was lost, and merges.

This is a presentation/location refactor. If any step would change what an
agent actually *does*, it's too aggressive — stop and surface it instead.
