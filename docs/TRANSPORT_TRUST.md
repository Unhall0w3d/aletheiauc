# Transport trust

HTTPS collection warns and continues without certificate verification by default
because many Cisco UC deployments use self-signed certificates. Use
`--verify-tls` with the system trust store or `--ca-bundle /path/to/customer-ca.pem`
when the environment supports verified TLS. `--ca-bundle` requires `--verify-tls`.

UCOS SSH rejects unknown host keys by default. After verifying a displayed host
fingerprint out of band, use `--accept-new-host-key` once to enroll the key in
the local known-hosts store. A changed key remains a failure requiring review.

These behaviors are fixture-tested. Private-CA and UCOS enrollment outcomes
must still be validated against each customer environment before production use.
