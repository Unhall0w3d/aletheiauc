# Engineering Hardening — Current-State Gap Analysis

Historical Phase 0 snapshot reviewed on 2026-07-12 against `main` at
`6b1b596c08cafee4c8149c12c3e81be7877e55e6`. Later hardening commits supersede
the matrix statuses where implementation has since landed.
The historical `03102c2` overlay was reviewed only as a source of hypotheses; none of
its replacement files were applied.

## Preflight

- Working tree: clean apart from the untracked, environment-owned `.codex_resume` file.
- Python: `.venv/bin/python` reports Python 3.14.6. The installed editable package points
  to another workspace, so source-tree tests use `PYTHONPATH=src`.
- Current verification: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`,
  `.venv/bin/ruff check src tests`, and `PYTHONPATH=src .venv/bin/python -m mypy src`.
- Packaging validation is currently incomplete: the virtual environment cannot import
  `setuptools.build_meta`, and the system Python lacks `pip`.

## Gap matrix

| Area | Classification | Current evidence and relevant symbols | Follow-up phase |
| --- | --- | --- | --- |
| Collector failure isolation | Partially resolved | `AssessmentEngine.run` converts ordinary collector exceptions, but `TargetPipelineCollector.collect` calls child collectors directly. A child failure can suppress later child collectors for that target. | 1 |
| Package runtime dependencies | Still present | `requirements.txt` lists Paramiko, while `[project].dependencies` in `pyproject.toml` does not. `transport.ssh.UcosSshSession` imports Paramiko in production. | 1 |
| CI/release artifact verification | Still present | `.github/workflows/tests.yml` tests only Python 3.11 from an editable checkout; it does not build/install wheel or source artifacts. | 1 |
| Artifact permissions/redaction/bundle metadata | Still present | `artifacts.py` uses default modes; API request/response text is redacted only with narrow regular expressions and CLI output is not redacted. Review ZIP manifests lack sensitivity/trust metadata. | 2 |
| HTTPS/SSH trust defaults | Still present | `TlsPolicy.verify` defaults to `False`; CLI describes insecure as the alpha default. `UcosSshSession` uses Paramiko `AutoAddPolicy`. The current first-use behavior is superseded by explicit enrollment. | 3 |
| Documentation and governance | Still present | `docs/` currently contains branding only. README and command help need a security/validation and support-boundary companion set. | 4 |
| Module decomposition | Outstanding, intentionally deferred | `reports/html.py` (2,139 lines), `config.py` (1,002), `application.py` (628), and `rules/basic.py` (617) are responsibility-dense. No safe broad move is required for hardening. | 5 plan only |
| UCOS command catalog | Partially resolved | `collectors.cuc_platform` has bounded, read-only commands and per-command timeouts, but selection remains a string tuple without stable metadata or applicability/sensitivity classification. | 5 small refactor |
| Product/package naming | No longer an immediate hardening defect | Public product and default command are AletheiaUC; distribution/import aliases remain compatibility debt. Do not rename package in this initiative. | 4 documentation |

## Dependency ordering and risks

1. Collector isolation, package metadata, and CI establish a trustworthy verification base.
2. Artifact handling must precede report/log bundle sharing guidance.
3. Transport defaults require explicit operator migration guidance and must not be hidden in a refactor.
4. Documentation is updated with each behavioral phase and reconciled after them.
5. Large-module moves remain separate from security-default changes.

## Live validation still required

- CUCM HTTPS with system trust, private CA, rejected self-signed certificate, hostname mismatch,
  expired certificate, and explicit insecure override.
- CUC UCOS known-host success, unknown-host rejection, verified first-use enrollment, and changed-key rejection.
- Extended UCOS command completion and partial-output behavior on real CUC versions.
- File permission behavior on Windows and operational review-ZIP sharing workflow.
