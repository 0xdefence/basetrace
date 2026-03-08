# BaseTrace Methodology (Phase 5)

## Labeling approach
BaseTrace uses rule-based heuristics first for explainability and fast iteration.
Each label includes:
- `label`
- `confidence` (0.0 to 1.0)
- `evidence` (rule id + supporting metrics)

## Initial label set
- deployer
- router
- bridge
- treasury
- exchange-facing
- unlabeled-high-activity

## Confidence model
Confidence is derived from rule strength and signal quality:
- strong deterministic match: 0.9-0.99
- multi-signal heuristic match: 0.7-0.89
- weak behavioral hint: 0.5-0.69

## Alert rules (v1)
1. fan_out_spike
2. fan_in_spike
3. new_high_centrality_node
4. anomalous_bridge_path

Each alert includes:
- `type`, `severity`, `confidence`
- `why_flagged` (rule explanation)
- `evidence` (window deltas, ratios, degree proxy)

## Limitations
- public RPC sources are rate-limited and may delay ingest
- heuristics can mislabel edge cases without human validation
- bridge anomaly logic depends on known bridge mappings

## Validation policy
- sampled manual label review weekly
- track precision over known entities
- tune thresholds to preserve high signal-to-noise
