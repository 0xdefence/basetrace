# Label Taxonomy Mapping (MVP)

This file defines explicit MVP coverage for entity clustering labels.

| Label | Source | Rule | Confidence |
|---|---|---|---|
| deployer | heuristic | `contracts_deployed >= 3` | `min(0.95, 0.6 + contracts_deployed*0.05)` |
| router | known + heuristic | known router contracts OR `tx_count > 500 && unique_counterparties > 200` | `0.98 known / 0.72 heuristic` |
| bridge | known | known Base bridge system contracts | `0.98` |
| treasury | known | known Base fee/treasury vault contracts | `0.98` |
| exchange-facing | heuristic | `inbound_edges > 500 && outbound_edges < inbound_edges * 0.15` | `0.67` |

Validation script:

```bash
python3 scripts/validate_label_taxonomy.py
```
