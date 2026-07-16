# Session State

Last updated: 2026-07-16

## Current Milestone

```text
0.4.x/0.5.x - CUCM Diagnostic Baseline Stabilization
```

## Current Focus

Stabilize the first live CUCM 15 diagnostic baseline and promote only
well-understood snapshot facts into conservative assessment output.

The immediate implementation focus is:

```text
Validate UUID-preserved route patterns and route-filter/dial-plan distinctions against CUCM 15.
Evaluate all returned certificates for expiration while treating phone-sast-trust
and phone-vpn-trust as optional stores whose absence is not a finding.
Promote stable RISPort70, Control Center, and PerfMon functions from diagnostic-only toward baseline collectors.
Keep report readiness ahead of broader feature expansion; CUC now has bounded
CUPI inventory plus UCOS platform-health summaries and conservative findings.
Assessment-group persistence, per-technology credential resolution, isolated
target pipelines/artifacts, and consolidated reporting are implemented and
awaiting a mixed CUCM/CUC live validation.
The interactive menu separates standard report-only assessments from explicit
diagnostic evidence-bundle assessments. It supports technology-owned connection
profiles, saved multi-technology assessment profiles, session settings with a
non-secret current-settings summary, and sequential SSH host-key preflight
before parallel collection.
```

## Recently Completed

```text
Project renamed from Helios to AletheiaUC
Repository made private
Proprietary license adopted
Python package retained as cisco_collab_health
Console commands: aletheiauc and ccha
Core architecture established
AXL foundation implemented
SOAP transport implemented
TLS policy implemented
AXL version retry/cache implemented
EvidenceRef implemented
Collector notes implemented
Collector errors made non-fatal
Collector health rule implemented
Report coverage helper implemented
HTML collection coverage section implemented
HTML collector notes and evidence sections implemented
HTML sections for all current fact categories implemented
Summary-first device inventory and registration report sections implemented
Detailed device inventory and registration tables moved toward report end
Synthetic sample report populated across current fact categories
Bounded AXL listPhone inventory implemented with page-size and max-device controls
DeviceLoadDefaultFact implemented
Device Load Summary report section implemented
Informational manual-load rule implemented
AXL listPhone duplicate-page stop implemented from live CUCM debug output
AXL listPhone page-specific artifact paths implemented
CollectionContext moved from collectors.base to models.runtime
CollectionResult status_flags added for structured coverage semantics
AXL collector helpers reorganized into collectors/axl package with compatibility shims
AXL listDevicePool enrichment implemented for device inventory
Detailed device inventory report expanded with call manager group and region
AXL device-default collection integrated with phone inventory
CUCM 15 live diagnostic run reviewed
RISPort70 registration responses normalized during diagnostic capture
Control Center service-status responses normalized during diagnostic capture
PerfMon baseline counter responses normalized during diagnostic capture
Configured-versus-runtime reconciliation added as informational-only output
Diagnostic API attempt ledger and per-operation raw request/response artifacts added
CUCM 15 Device Defaults faults established that name/UUID—not model/protocol—drives discovery
Report captions, load-data availability, and reconciliation caveats refined from live output
RISPort runtime firmware/download and registration diagnostics normalized
RISPort model codes enriched with AXL model names
Control Center service catalog metadata joined to service status
PerfMon counter instances retained and two-sample diagnostic collection implemented
Bounded AXL dial-plan, trunk, topology, and media-resource lists normalized
Large service/performance/configuration details made collapsible with concise summaries
Runtime firmware distribution and explicit download-failure finding implemented
Non-started services summarized by Control Center reason
Zero-only CPU snapshots marked unavailable
Device Pool relationships normalized into configuration inventory
Detailed device and registration tables made collapsible
Customer-facing HTML policy implemented: operational identifiers are retained while
engineering-only evidence and collection mechanics are omitted
Opt-in Downloads-folder review ZIP export implemented for self-contained log bundles
Bounded configured-model Device Defaults SQL collection implemented
Detailed registration download-failure reason column added
Service summaries grouped by node and service group
Inventory-only reconciliation conservatively separates known non-runtime templates
Memory snapshots explicitly labeled observational with no health threshold
All nonblank AXL Phone Load values classified as static overrides
Static overrides subdivided by current Device Default relationship
Configured/static/default loads correlated with RISPort active firmware
Runtime firmware distribution summarized by model and protocol
Non-firmware CTI runtime objects excluded from firmware analysis
Failure-aware configured/default/active firmware correlation implemented
Mixed active firmware populations and actionable exception detail implemented
Device Defaults SQL count explicitly modeled as configured model count
Firmware download rule split into active-mismatch warning and status-only information
Firmware exception impact and configured/runtime population context added
Conservative service runtime rule excludes known intentional stopped states
Inventory-only summaries by model and device pool implemented
Nested AXL diagnostic membership capture implemented for CSS, route lists, and route groups
Route-pattern destination and dial-plan relationship reporting implemented
Observed cross-node service deployment comparison implemented
Wide report tables made responsive and large relationship matrices collapsible
Per-node UC Certificate Management REST snapshot capture implemented
Certificate identity/trust fact, rule, and report scaffolding implemented; live PEM decoding pending
Expired/60-day certificate rule/report scaffolding implemented; live PEM normalization pending
Legacy encrypted profiles prompt for and persist missing OS/SSH credentials
Certificate API 401 output distinguishes CMPlatform authorization from missing credentials
Encrypted profiles explicitly track whether Platform/CLI credentials were intentionally configured
Certificate Management REST Platform authentication live-validated on all three CUCM nodes
Live certificate schema established: identities[].certificate and trusts[].certificate_data[].certificate contain PEM
Latest snapshot contains 22 identity instances and 144 trust instances (54 unique trust certificates)
Strict mypy passing
ruff passing
Automated unit suite passing (231 tests as of 2026-07-16)
CI added
Guided menu refactored into standard and diagnostic run modes with explicit confirmation
Guided profile management groups technology connection profiles and saved assessment profiles
Assessment profiles can be copied, revised from their preselected membership, and saved separately
```

## Immediate Next Work

```text
1. Validate all 88 UUID-keyed route patterns survive normalization and inspect
   route-filter/dial-plan fields for the same-pattern/same-partition pairs.
2. Confirm certificate findings show filenames, stores, and all affected nodes.
3. Confirm the false post-validation preflight warning is absent.
4. Close remaining CUCM 15 regressions, then start CUCM 14.x validation.
```

## Do Not Start Yet

```text
CLI fallback framework
GUI work
```

Dedicated, non-diagnostic RISPort70, Control Center, and PerfMon collectors
remain future work. Their diagnostic implementations may be promoted only after
cross-version validation and explicit coverage semantics are defined.
