---
description: Print the object-specific validator (if one exists) and the universal system validators, before building a transform for an object.
allowed-tools: Bash(.venv/Scripts/python.exe cli.py check-validators *)
---
Check validators for `$ARGUMENTS` (an object name).

1. Run: `.venv/Scripts/python.exe cli.py check-validators $ARGUMENTS`
2. Paste the actual output — the system validator list plus the object's
   own entry (or the "none found yet" note) are the point, not a summary.
3. If nothing exists yet for this object and this build turns up a real,
   object-specific gotcha, write it into `validators/<Object>.md` before
   moving on — see `validators/README.md` for the format, including the
   required OKF frontmatter (`type: ObjectValidator` plus
   title/description/tags/timestamp) and the matching `index.md`/`log.md`
   entries every new validator needs.

Read-only, no confirmation needed.
