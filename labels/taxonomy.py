LABEL_TAXONOMY = {
    "deployer": {
        "source": "heuristic",
        "description": "Address deploys multiple contracts.",
        "rule": "contracts_deployed >= 3",
        "confidence_model": "min(0.95, 0.6 + contracts_deployed * 0.05)",
    },
    "router": {
        "source": "known+heuristic",
        "description": "High-throughput routing behavior or known infra/router contract.",
        "rule": "known label OR (tx_count > 500 AND unique_counterparties > 200)",
        "confidence_model": "0.98 known, 0.72 heuristic",
    },
    "bridge": {
        "source": "known",
        "description": "Known bridge-system contracts.",
        "rule": "address in BASE_KNOWN_LABELS with value=bridge",
        "confidence_model": "0.98",
    },
    "treasury": {
        "source": "known",
        "description": "Known protocol treasury/vault system contracts.",
        "rule": "address in BASE_KNOWN_LABELS with value=treasury",
        "confidence_model": "0.98",
    },
    "exchange-facing": {
        "source": "heuristic",
        "description": "Collects large inbound flow relative to outbound edges.",
        "rule": "inbound_edges > 500 AND outbound_edges < inbound_edges * 0.15",
        "confidence_model": "0.67",
    },
}
