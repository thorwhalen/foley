---
description: Sound-design a narration with foley — choose SFX for the text and weave them in.
---
Sound-design the following narration using the `foley` package and the `foley-sound-design`
skill. Exercise restraint — most sentences need no sound.

$ARGUMENTS

Steps:
1. Load the `foley-sound-design` skill (or call the `foley_guide` MCP tool) for the workflow and
   the taste heuristics.
2. Choose sounds with `foley.score(segments, ...)` (or the `find → plan` loop). Only place a
   sound where it adds meaning; honor the fail-closed license gate.
3. Show the rationale and the editable timeline. If the narration audio is available, weave it
   (`foley.weave(narration, timeline)` / the `foley_weave` tool) into a mastered mix + captions.
4. Report the chosen sounds, their licenses, and the credits (`foley.credits(...)`).
