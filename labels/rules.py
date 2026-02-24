"""Labeling heuristics v1."""

from labels.known_entities import BASE_KNOWN_LABELS


def label_address(address: str, features: dict) -> list[dict]:
    a = (address or "").lower()
    labels = []

    if a in BASE_KNOWN_LABELS:
        labels.append({
            "label": BASE_KNOWN_LABELS[a],
            "confidence": 0.98,
            "evidence": {"source": "base_known_system_contracts"},
        })

    tx_count = int(features.get("tx_count", 0) or 0)
    contracts_deployed = int(features.get("contracts_deployed", 0) or 0)
    unique_counterparties = int(features.get("unique_counterparties", 0) or 0)
    inbound_edges = int(features.get("inbound_edges", 0) or 0)
    outbound_edges = int(features.get("outbound_edges", 0) or 0)

    if contracts_deployed >= 3:
        labels.append({
            "label": "deployer",
            "confidence": min(0.95, 0.6 + contracts_deployed * 0.05),
            "evidence": {"contracts_deployed": contracts_deployed},
        })

    if tx_count > 500 and unique_counterparties > 200:
        labels.append({
            "label": "router",
            "confidence": 0.72,
            "evidence": {"tx_count": tx_count, "unique_counterparties": unique_counterparties},
        })

    if inbound_edges > 500 and outbound_edges < inbound_edges * 0.15:
        labels.append({
            "label": "exchange-facing",
            "confidence": 0.67,
            "evidence": {"inbound_edges": inbound_edges, "outbound_edges": outbound_edges},
        })

    if tx_count > 1000 and outbound_edges > 500 and inbound_edges > 500:
        labels.append({
            "label": "high-activity",
            "confidence": 0.6,
            "evidence": {"tx_count": tx_count},
        })

    return labels
