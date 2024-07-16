# Contributing to Emma

## Changelog Requirements

Emma utilizes a tool called [`towncrier`](https://towncrier.readthedocs.io/) for changelog management and generation.
What this means in practice for contributing to Emma is:

1. Any PR to the `main` (or `develop`) branch must contain at least one Markdown formatted `newsfragment` file in the directory `emma/changelog.d`
1. This file should be named with format `<github issue id>.<change type>.md`. For example:
    * Newsfragment file named `1234.fixed.md` represents a PR closing Github Issue #1234, which is a bugfix
    * This allows `towncrier` to populate the correct section of the release notes with the relevant information.
1. Newsfragment files should follow the standards of [Keep a Changelog](https://keepachangelog.com/); available change types (e.g. Newsfile suffixes) are:
    1. **Added** for new features.
    1. **Changed** for changes in existing functionality.
    1. **Deprecated** for soon-to-be removed features.
    1. **Removed** for now removed features.
    1. **Fixed** for any bug fixes.
    1. **Security** in case of vulnerabilities.
1. Upon release of a new version, maintainers (and eventually CI) will execute `towncrier` which will do the following:
   1. Consolidate all Newsfragment files in the `emma/changelog.d` directory into a single file named `CHANGELOG.md` (automatically prepending the changelog into the relevant release section)
   1. `git rm` all individual Newsfragment files
