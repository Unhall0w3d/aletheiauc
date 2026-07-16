# Development Workflow

## Default Work Loop

```text
1. Define the engineering question.
2. Identify source of truth.
3. Collect raw data through API or CLI.
4. Store/redact raw evidence.
5. Parse into normalized facts.
6. Add or update health rules.
7. Render facts/findings in HTML and JSON reports.
8. Add fixture tests.
9. Run ruff, mypy, and unit tests.
10. Review generated report visually.
```

## Report-Integrated Workflow

When a collector is added, the report must be updated in the same feature sequence.

Done means:

```text
raw artifact captured
parser tested
facts populated
report section updated
JSON output contains facts
HTML output shows facts
findings produced if appropriate
```

## Quality Gates

Before committing:

```bash
PYTHONPATH=src python -m unittest discover -s tests
ruff check .
PYTHONPATH=src .venv/bin/mypy src
```

If the active shell environment does not provide `.venv/bin/mypy`, this is also acceptable:

```bash
PYTHONPATH=src python -m mypy src
PYTHONPATH=src python -m unittest discover -s tests
```

## Live CUCM Testing

Unit tests must not require live CUCM.

Live testing should be manual/integration only and should use sanitized artifacts for fixtures.

For the private test/review/iterate workflow, use:

```bash
./aletheiauc.py --diagnostic-capture --export-review-zip
```

This writes the self-contained troubleshooting bundle to the current user's
Downloads folder. The ZIP is private diagnostic evidence and can contain
customer identifiers even when the HTML report uses customer-safe presentation.

For a guided live run, start `./aletheiauc.py`, configure any session settings,
then select **Run diagnostic assessment**. The standard guided run produces only
the paired engineering and customer-facing HTML reports; it is not the review
bundle workflow.


## Report-Integrated Feature Completion

For AletheiaUC, a collector or parser change is not considered complete until the related report output has been reviewed.

Use this cycle:

```text
collect
parse
normalize
evaluate
report
review
adjust
```

This keeps reporting, parsing, and data collection aligned as the project grows.
