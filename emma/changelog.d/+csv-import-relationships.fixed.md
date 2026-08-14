CSV imports can now reference a related object by its human-friendly ID alone, for
example `rtp1` in a `site` column, which is resolved under the kind the relationship
points at. Previously the first `__`-separated segment of the value was always read as a
kind name, so a bare human-friendly ID was either dropped from the import or raised
`SchemaNotFoundError`. The `Kind__identifier` form still works and is still needed to
reference a peer through a relationship to a generic.
