# Emma Changelog

This is the changelog for Emma.
All notable changes to this project will be documented in this file.

Issue tracking is located in [Github](https://github.com/opsmill/emma/issues).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This project uses [*towncrier*](https://towncrier.readthedocs.io/) and the changes for the upcoming release can be found in <https://github.com/opsmill/emma/tree/main/emma/changelog.d/>.

<!-- towncrier release notes start -->

## [0.7.0](https://github.com/opsmill/emma/tree/0.7.0) - 2026-08-14

### Changed

- Dependencies updated, including security fixes for aiohttp, dulwich, pillow,
  pydantic-settings, python-dotenv, ujson and urllib3, and for 16 packages in the docs
  build. Streamlit moves to 1.61, which brings pandas 3 and drops tornado. `pytz` is now
  declared explicitly: it is imported directly by Emma but had only ever arrived
  transitively through pandas, which no longer depends on it.

### Fixed

- A CSV import that failed no longer reports success. Rows rejected by Infrahub are now
  counted, and the result names how many of the file's rows were imported. Previously
  every row could be rejected and the import still ended with "Loading completed with
  success".
- A column that matches nothing in the schema no longer blocks a CSV import. It is
  reported as a warning, left out of the data sent to Infrahub, and the rest of the file
  is imported. Validation messages are now shown inline instead of only as toasts, which
  faded after a few seconds and left the page blank with no indication of the problem.
- CSV imports can now reference a related object by its human-friendly ID alone, for
  example `rtp1` in a `site` column, which is resolved under the kind the relationship
  points at. Previously the first `__`-separated segment of the value was always read as a
  kind name, so a bare human-friendly ID was either dropped from the import or raised
  `SchemaNotFoundError`. The `Kind__identifier` form still works and is still needed to
  reference a peer through a relationship to a generic.
- Surrounding whitespace in CSV headers and values is now stripped. A header with a
  trailing space, such as `height_u` followed by a space, previously failed to match the
  schema, and the resulting message was indistinguishable from a genuinely misnamed column
  because the space was invisible. Names are now quoted in messages.
- The Data Exporter no longer fails on an object whose related peer is absent from the
  client's store. The lookup that allows a miss had its result used without checking it,
  so a miss raised `AttributeError` instead of falling back to the peer's ID.
- The Template Builder now reports a Jinja2 syntax error with its line number instead of
  raising. The error path passed the exception to a helper that expects a rich traceback
  and returns a list of frames, then concatenated that list onto a string, so checking a
  template with a syntax error could only ever fail.

## [0.2.0](https://github.com/opsmill/emma/tree/0.2.0) - 2024-07-16

### Added

- Added the tool [`towncrier`](https://towncrier.readthedocs.io/) to manage changelog creation.

  See the `CONTRIBUTING.md` file for more information and usage instructions. ([#4](https://github.com/opsmill/emma/issues/4))

## [0.1.0](https://github.com/opsmill/emma/tre/0.1.0) - 2024-07-07

### Added

- Initial commit and functionality!
