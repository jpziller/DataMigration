---
description: Surface the OKF knowledge (target-platform behavior + external recipe sources) relevant to the objects or cloud in play, before building.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py gather-okf *)
---
Gather relevant OKF knowledge for `$ARGUMENTS`.

`$ARGUMENTS` is typically one or more object names; you can also pass
`--subject-area <area>` (e.g. `nonprofit-cloud`, `synthetic-data-recipes`)
to list a whole cloud/topic.

1. Run: `.venv/Scripts/python.exe cli.py gather-okf --objects $ARGUMENTS`
   (or `.venv/Scripts/python.exe cli.py gather-okf --subject-area $ARGUMENTS`
   when the argument is a subject area, not object names).
2. Paste the actual output — the list of relevant OKF docs with their
   type/tags/source/summary is the point, not a paraphrase.
3. **Actually read the docs it points at** before building a transform or a
   new cloud's sample-data recipe. This bundle exists so target-platform
   behavior (auto-created records, platform validations, real
   join/cardinality quirks) and any vetted external recipe are consulted up
   front — not rediscovered on a live org after a failed load. Don't gloss
   past a relevant hit.
4. If you learn something durable that isn't captured yet, add it to
   `okf/<cloud>/` (or `validators/<Object>.md` for a tooling-specific
   gotcha) — with OKF frontmatter and the matching `index.md`/`log.md`
   entries — so the next pass doesn't rediscover it.

Read-only, no confirmation needed, no org connection required.
