"""Labeling heuristics scaffold."""


def label_address(features: dict) -> list[dict]:
    labels = []
    # TODO examples:
    # - deployer: high contracts_created
    # - router: high unique counterparties + swap signatures
    # - bridge: known bridge contracts + cross-domain events
    return labels
