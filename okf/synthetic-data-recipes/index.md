# Synthetic-data recipes (external sources + coverage)

Knowledge about **where vetted, shareable synthetic-data recipes already
exist** for a given Salesforce cloud/product — so a migration doesn't
re-derive a recipe (and re-hit known issues) that the ecosystem has
already solved and published.

This is the OKF **describe-and-link** side of the framework's own
`sample_data/` recipe files: `sample_data/` holds the recipes this repo
actually ships and runs; this subject area **catalogs the upstream
sources** (Salesforce.org's own recipe libraries, CumulusCI datasets,
community collections) with `resource:` links, per the OKF convention of
citing a source rather than copying it.

The point is **heading off issues before they happen**: before authoring a
new cloud's recipe — or building transforms against an unfamiliar target —
check whether an upstream recipe already encodes that cloud's real object
relationships and cardinalities. Where one exists, start from it and layer
this repo's own empirically-learned behavior on top; where it doesn't
(most commercial/industry clouds today), that's the signal to build and
own it here.

# References

* [External Snowfakery recipe sources — catalog + per-cloud coverage](external-recipe-sources.md) -
  the shared recipe libraries (SFDO community, CumulusCI, Snowfakery
  itself), what each covers, the real coverage gaps (Consumer Goods,
  Sales, Service are largely uncovered), and the crucial limit: upstream
  recipes give you *structure*, not the *auto-creation/behavior* layer
  this repo captures empirically.
