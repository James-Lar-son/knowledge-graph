# Taguette cheat sheet — coding for the knowledge graph

Keep this next to Taguette. Codebook imported: **core only** (32 tags —
27 `r.` predicates + 5 `m.` meta). Every `n.` / `s.` tag you create
yourself, as you go.

## Recipes — the tag combos that cover almost everything

| You found… | Tag the highlight with |
|---|---|
| A passage proving a skill / method | `r.demonstrates` + `n.skill.<slug>` (or `n.meth.<slug>`) |
| A passage backing a claim | `r.supports` + `n.claim.<slug>` |
| A passage expressing a value | `r.expresses` + `n.val.<slug>` |
| A passage situated in an era | `r.during_era` + `n.era.<slug>` — or just the `n.era.` tag alone, era is a default |
| A paper resting on a theory / contribution | `s.pub.<slug>` + `r.grounded_in` + `n.thy.<slug>` (or `n.ctb.<slug>`) |
| One paper citing / extending another | `s.pub.<slug>` + `r.cites` (or `r.extends`) + `n.pub.<slug>` |
| A person in a role | `s.person.<slug>` + `r.held_role` + `n.role.<slug>` |
| A genuinely new node | Use its would-be ID as the `n.` tag anyway — ingest proposes it for review instead of merging it silently |
| A gap / open question | `m.prov.prompt` + the `n.` tag it concerns |

No `s.` tag = the span itself becomes a new Evidence node. No `r.` tag =
ingest defaults where unambiguous (Skill/Method→`demonstrates`,
Claim→`supports`, Value→`expresses`, Era→`during_era`) and flags it.

## Prefixes — the prefix *is* the type

`person` Person · `org` Organization · `role` Role · `era` Era ·
`pub` Publication · `artifact` Artifact · `skill` Skill · `meth` Method ·
`thy` Theory · `ctb` Contribution · `prn` Principle · `val` Value ·
`mot` Motivation · `theme` Theme · `aud` Audience · `prob` Problem ·
`proc` Process · `place` Place · `purp` Purpose · `niche` Niche ·
`ev` Evidence · `gap` Evidence (a gap) · `claim` Claim · `src` Source

Exact IDs for all 277 existing nodes: `node_tags.csv` — search it before
creating a tag. Typo safety net: a mistyped ID just shows up in my
staging report as a "new node proposed," where we'll catch it — it can't
silently corrupt the graph.

## Meta tags

`m.layer.private` / `m.layer.public` — override the source's layer
(sources from 2020+ default to private anyway) ·
`m.prov.inferred` / `m.prov.prompt` — override verified ·
`m.evidence` — also make an Evidence node when an `s.` tag is present.

## When you're done coding a document

Export Highlights → CSV (or the whole project as `.sqlite3`), drop it in
`knowledge-graph/inbox/` or hand it to me in chat. I run the dry-run,
show you the staging report, and only merge on your go.
