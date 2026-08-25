"""
Builds a customer-to-customer relationship graph from shared infrastructure
(devices, IPs, coupons) seen across transactions, using NetworkX.

Two customers get an edge if they've both transacted using the same device,
IP, or coupon. Edge weight = total number of shared entities. This graph is
the input to abuse-ring detection in the next step - here we only build it
and sanity-check that it actually captures the injected ring signal.

ring_id from customers.csv is used ONLY for a diagnostic sanity-check print
at the end - it is never used to build the graph itself.

Run with (from ml-service/, venv active):
    python -m graph_engine.build_graph
"""

import itertools
import os
import sys
from collections import defaultdict

import networkx as nx
import pandas as pd

from graph_engine import config


def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(config.RAW_DIR, filename)
    if not os.path.exists(path):
        print(f"❌ Missing required file: {path}")
        print("   Run Step 6's generator first: python -m data_generation.generate_dataset")
        sys.exit(1)
    return pd.read_csv(path)


def build_shared_edges(transactions: pd.DataFrame, entity_types: list) -> dict:
    """
    For each entity type (device_id, ip_id, coupon_id), groups transactions
    by that entity and connects every pair of distinct customers who used it.
    Returns: { (customer_a, customer_b): {"device_id": n, "ip_id": n, "coupon_id": n} }
    with customer_a < customer_b alphabetically to avoid double-counting pairs.
    """
    edge_counts = defaultdict(lambda: {etype: 0 for etype in entity_types})

    for entity_type in entity_types:
        valid_txns = transactions.dropna(subset=[entity_type])
        grouped = valid_txns.groupby(entity_type)["customer_id"].apply(lambda s: sorted(set(s)))

        for customers_sharing_entity in grouped:
            if len(customers_sharing_entity) < 2:
                continue
            for customer_a, customer_b in itertools.combinations(customers_sharing_entity, 2):
                edge_counts[(customer_a, customer_b)][entity_type] += 1

    return edge_counts


def build_graph(all_customer_ids: list, edge_counts: dict) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(all_customer_ids)

    for (customer_a, customer_b), counts in edge_counts.items():
        weight = sum(counts.values())
        graph.add_edge(customer_a, customer_b, weight=weight, **counts)

    return graph


def compute_node_features(graph: nx.Graph, transactions: pd.DataFrame) -> pd.DataFrame:
    component_map = {}
    component_size_map = {}
    for component_id, component_nodes in enumerate(nx.connected_components(graph)):
        for node in component_nodes:
            component_map[node] = component_id
            component_size_map[node] = len(component_nodes)

    device_counts = transactions.groupby("customer_id")["device_id"].nunique()
    ip_counts = transactions.groupby("customer_id")["ip_id"].nunique()

    rows = []
    for node in graph.nodes():
        neighbor_weights = [graph[node][nbr]["weight"] for nbr in graph.neighbors(node)]
        rows.append({
            "customer_id": node,
            "graph_degree": graph.degree(node),
            "graph_weighted_degree": sum(neighbor_weights),
            "graph_max_edge_weight": max(neighbor_weights) if neighbor_weights else 0,
            "connected_component_id": component_map.get(node, -1),
            "connected_component_size": component_size_map.get(node, 1),
            "num_distinct_devices_used": int(device_counts.get(node, 0)),
            "num_distinct_ips_used": int(ip_counts.get(node, 0)),
        })

    return pd.DataFrame(rows)


def print_ring_sanity_check(customers: pd.DataFrame, node_features: pd.DataFrame) -> None:
    """
    Diagnostic-only check: for each real ring, what fraction of its members
    ended up in the SAME connected component? ring_id was never used to
    build the graph - this only checks afterward whether the graph
    independently rediscovered the injected structure.
    """
    print("\nSanity check - did the graph independently rediscover known rings?")
    print("(Diagnostic only - ring_id was never used to build the graph.)")

    merged = customers.merge(node_features, on="customer_id", how="left")
    ring_ids = sorted(merged["ring_id"].dropna().unique())

    for ring_id in ring_ids:
        ring_members = merged[merged["ring_id"] == ring_id]
        component_ids = ring_members["connected_component_id"].dropna()
        if component_ids.empty:
            print(f"   {ring_id}: no members found in the graph")
            continue
        most_common_component = component_ids.mode().iloc[0]
        matching = (component_ids == most_common_component).sum()
        pct = matching / len(ring_members) * 100
        print(f"   {ring_id}: {matching}/{len(ring_members)} members ({pct:.1f}%) "
              f"share the same connected component")


def main():
    print("FraudRing entity relationship graph construction")
    print("=" * 50)

    customers = load_csv("customers.csv")
    transactions = load_csv("transactions.csv")

    print("Finding shared infrastructure across transactions...")
    edge_counts = build_shared_edges(transactions, config.SHARED_ENTITY_TYPES)
    print(f"Found {len(edge_counts):,} customer pairs sharing at least one entity")

    print("Building graph...")
    graph = build_graph(list(customers["customer_id"]), edge_counts)
    print(f"Graph has {graph.number_of_nodes():,} nodes and {graph.number_of_edges():,} edges")

    print("Computing per-customer graph features...")
    node_features = compute_node_features(graph, transactions)

    num_components = node_features["connected_component_id"].nunique()
    largest_component = node_features["connected_component_size"].max()
    connected_customers = (node_features["connected_component_size"] > 1).sum()
    print(f"   {num_components:,} connected components total")
    print(f"   {connected_customers:,} customers share infrastructure with at least one other customer")
    print(f"   Largest connected component has {largest_component:,} members")

    print_ring_sanity_check(customers, node_features)

    try:
        os.makedirs(config.GRAPH_OUTPUT_DIR, exist_ok=True)

        edges_path = os.path.join(config.GRAPH_OUTPUT_DIR, "customer_edges.csv")
        edge_rows = [
            {"customer_a": a, "customer_b": b, "weight": sum(counts.values()), **counts}
            for (a, b), counts in edge_counts.items()
        ]
        pd.DataFrame(edge_rows).to_csv(edges_path, index=False)
        print(f"\n✅ Edge list saved -> {edges_path}")

        features_path = os.path.join(config.GRAPH_OUTPUT_DIR, "graph_features.csv")
        node_features.to_csv(features_path, index=False)
        print(f"✅ Node features saved -> {features_path}")
    except OSError as error:
        print(f"❌ Failed to save graph outputs: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()