<!-- Thanks for contributing! Please fill in what's relevant and delete the rest. -->

## What does this change?

<!-- One or two sentences. Focus on the user-visible behavior, not the diff. -->

## Why?

<!-- Link the issue if there is one (e.g. "Closes #42"). -->

## How to test

<!-- The exact commands a reviewer should run to verify the change. -->

```bash
# example
pytest tests/test_scanner.py -v
```

## Checklist

- [ ] Tests added or updated
- [ ] CHANGELOG entry added (under `## [Unreleased]` or the next version)
- [ ] If a new ecosystem is supported, both `PROJECT_MARKERS` and
      `ARTIFACT_PATTERNS` were updated
- [ ] CI is green on Linux / macOS / Windows for Python 3.10 / 3.11 / 3.12
