# Transport trust

HTTPS certificate verification is enabled by default. Use the system trust
store or `--ca-bundle /path/to/customer-ca.pem` for private Cisco PKI. Use
`--insecure` only for a deliberate, documented lab exception; it cannot be
combined with `--ca-bundle`.

UCOS SSH rejects unknown host keys by default. After verifying a displayed host
fingerprint out of band, use `--accept-new-host-key` once to enroll the key in
the local known-hosts store. A changed key remains a failure requiring review.

These behaviors are fixture-tested. Private-CA and UCOS enrollment outcomes
must still be validated against each customer environment before production use.
