# Security and data handling

Assessment artifacts, JSON reports, run logs, and review ZIPs are private
diagnostic material. On POSIX systems, AletheiaUC-created diagnostic directories
use owner-only permissions and created files use owner-readable/writable
permissions. API and CLI evidence uses the configured `secrets` redaction mode
by default; `none` retains raw evidence and requires deliberate operator care.

`--customer-safe-report` applies only to the HTML presentation. It does not
make adjacent JSON, logs, artifacts, or review ZIPs safe to share. Review every
bundle before external transfer and remove it according to the customer’s data
retention policy.
