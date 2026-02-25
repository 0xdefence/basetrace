#!/usr/bin/env python3
"""Validate MVP taxonomy coverage and heuristic consistency."""

from labels.rules import label_address
from labels.taxonomy import LABEL_TAXONOMY
from labels.known_entities import BASE_KNOWN_LABELS

REQUIRED = {"deployer", "router", "bridge", "treasury", "exchange-facing"}


def assert_required_taxonomy():
    missing = REQUIRED - set(LABEL_TAXONOMY.keys())
    if missing:
        raise SystemExit(f"Missing taxonomy labels: {sorted(missing)}")


def labels_for(features, address="0x000000000000000000000000000000000000dead"):
    out = label_address(address, features)
    return {x["label"] for x in out}


def assert_heuristics():
    # deployer
    assert "deployer" in labels_for({"contracts_deployed": 5, "tx_count": 10, "unique_counterparties": 2, "inbound_edges": 1, "outbound_edges": 1})
    # router heuristic
    assert "router" in labels_for({"contracts_deployed": 0, "tx_count": 800, "unique_counterparties": 250, "inbound_edges": 10, "outbound_edges": 10})
    # exchange-facing heuristic
    assert "exchange-facing" in labels_for({"contracts_deployed": 0, "tx_count": 20, "unique_counterparties": 3, "inbound_edges": 800, "outbound_edges": 20})


def assert_known_coverage():
    known_values = set(BASE_KNOWN_LABELS.values())
    for k in ["bridge", "treasury", "router"]:
        if k not in known_values:
            raise SystemExit(f"Known entity map missing expected class: {k}")


def main():
    assert_required_taxonomy()
    assert_heuristics()
    assert_known_coverage()
    print("PASS: taxonomy coverage and heuristic checks")


if __name__ == "__main__":
    main()
