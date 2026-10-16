# How many of the 608 edges can be inferred from the nodes alone?

Audit of `graph.working.json`, 2026-10-16. Method: for each candidate
rule, generate the edges the rule predicts from node fields (or from a
structural convention) and check them against the graph's actual edges,
counting an edge as inferred only on an exact match — including the
`via` field on multiedges. No fuzzy or label-based guessing counted.

## Tier 1 — exactly duplicated in node fields: 179 edges (29.4%)

| Predicate | Inferred / total | Rule |
|---|---|---|
| `during_era` | 62 / 62 | the node's own `era` field — a perfect two-way duplicate |
| `documented_in` | 56 / 142 | the node's `source` field (every `source` field has its edge; but 86 `documented_in` edges exist for nodes that carry no `source` field) |
| `authored` | 23 / 31 | a Publication's `authors` list (the other 8 are Person→Artifact, and Artifacts have no author field) |
| `role_at` | 21 / 21 | the Role node's `org` field — perfect duplicate |
| `coauthored_with` | 16 / 16 | pairs in a Publication's `authors` list where James is an author, `via` = the publication |
| `part_of` | 1 / 3 | an Organization's `parent` field (only one node carries it) |

Near-miss worth knowing: `pub:laplace_hack` lists only Cecilia La Place
as author, so it correctly produces *no* co-authorship edge — the rule
has to require James in the author list, not just pair up authors.

## Tier 2 — structural convention: +21 edges (200 total, 32.9%)

`held_role` 21 / 21. Every Role node in the graph is a role James held,
and every `held_role` edge runs from `person:james_larson` to exactly
the set of all Role nodes. In a single-subject graph that's derivable
from the node set alone, but it rests on a convention ("all Roles are
his"), not on data stored in the nodes — so it's counted separately.

## The rest — 408 edges (67.1%) — are not in the nodes at all

These exist only as edges. They are the graph's actual assertions, and
they're concentrated in its semantic core:

`expresses` 89 · `demonstrates` 67 · `supports` 38 · `grounded_in` 32 ·
`recurs_as` 15 · `applies_method` 12 · `composes_niche` 10 ·
`contradicts` 8 · the remaining `documented_in` 86 and
`authored` (→Artifact) 8 · everything else in single digits.

## What this means for growing the graph

- **A third of the graph is bookkeeping.** If nodes are created with
  their `era`, `source`, `org`, and `authors` fields filled, those 179
  edges never need to be coded by hand — a generator can emit them and
  the result matches the existing graph exactly.
- **The other two-thirds are the knowledge.** No field, convention, or
  closure rule recovers `demonstrates` / `expresses` / `supports` /
  `grounded_in` — which is exactly why the Taguette coding (the part
  only a reader can assert) is aimed at them, and why the ingest
  auto-adds only `documented_in` today.
- Candidate follow-on: teach the ingest to also auto-emit Tier-1 edges
  when a proposed new node arrives with its fields attached (e.g. a new
  Role with `org` + `era`, a new Publication with `authors`).
