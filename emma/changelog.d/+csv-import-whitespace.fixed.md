Surrounding whitespace in CSV headers and values is now stripped. A header with a
trailing space, such as `height_u` followed by a space, previously failed to match the
schema, and the resulting message was indistinguishable from a genuinely misnamed column
because the space was invisible. Names are now quoted in messages.
