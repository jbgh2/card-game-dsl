# Move-level visibility

**Tier 3 — medium impact, narrow scope.**

Zone declarations set default projections; move clauses override.
Override semantics is "the move's clause replaces the zone
projection for this event only." Cases like "downgrade further but
keep the zone's projection for everything not mentioned" might
want different semantics. No corpus example has hit this yet.
