Surrounding whitespace in CSV headers and values is now stripped. A header such as
`height_u ` previously failed to match the schema, and the resulting message was
indistinguishable from a genuinely misnamed column because the trailing space was
invisible.
