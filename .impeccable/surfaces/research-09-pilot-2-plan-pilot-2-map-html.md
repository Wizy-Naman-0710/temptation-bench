---
version: 1
slug: "research-09-pilot-2-plan-pilot-2-map-html"
primary_target: "research/09-pilot-2-plan/pilot-2-map.html"
related_targets: []
---

# Pilot-2 simulation map

Scope: one page, `research/09-pilot-2-plan/pilot-2-map.html`, also published as a claude.ai artifact. Mode: Read.

Audience and job: the project owner (a student, new to agents) uses it to understand and check the pilot-2 plan before the build. Owner feedback: the old hand-drawn map was unreadable (handwriting font, too much at once, weak dark-mode colours). Owner chose "overview, then zoom".

Content: 40 parts, 27 connections, 6 step-through flows, 32 tools, files and build steps, all from 00-README and notes 01–05. Everything is a proposal; the bank name never appears ({BANK} only).

## Direction contract

FORM: Operations Manual (a bank's tabbed procedure binder with swimlane process charts). seed:d809d5d153d18bff
THESIS: The simulation explained the way a bank explains itself: index tabs per department, a swimlane process chart per flow. Refuses the one giant everything-at-once board.
OWN-WORLD: cool white ground, navy ink, one colour per department used only on tabs and lane chips; ruled swimlanes, crisp 2px ink boxes, document numbers (e.g. H-03) on every part. Dark mode = navy-black ground, lighter tab hues, same ink logic.
STORY: Overview tab: five lanes, ~10 key parts, the main path. Each department tab: its own lane chart with all its parts, then a reference list. Click a part → details panel. Flows play as highlighted paths with a step spine.
FIRST VIEWPORT: document number line, title, one-sentence lede, tab row, overview swimlane chart with key.
SIGNATURE: arrow stroke = meaning (solid call, dashed wake/timer, double data written); dashed box = not built yet; a numbered step spine on flows.
RISK: paperwork feel if tabs are timid; the chart must carry the page.
