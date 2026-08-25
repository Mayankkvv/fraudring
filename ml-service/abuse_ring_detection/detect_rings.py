"""
Detects candidate abuse rings by removing "hub" entities (shared by too
many unrelated customers to be meaningful evidence of coordination) from
the raw graph, then finding connected components / communities in what
remains.

ring_id is used ONLY to evaluate how well this detection matches the known
ground truth afterward - it is never used to build the clusters themselves.

Run with (from ml-service/, venv active):
    python -m abuse_ring_detection.detect_rings
"""

import itertools
import os
import sys
from collections import defaultdict

import networkx as nx
import pandas as pd
from networkx.algorithms.community import greedy_modularity_communities

from abuse_ring_detection import config


def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(config.RAW_DIR, filename)
    if not os.path.exists(path):
        print(f"❌ Missing required file: {path}")
        print("   Run Step 6's generator first: python -m data_generation.generate_dataset")
        sys.exit(1)
    return pd.read_csv(path)


def identify_hub_entities(transactions: pd.DataFrame, entity_type: str, max_sharers: int):
    """
    Returns the set of entity values (e.g. specific device_ids) used by MORE
    than `max_sharers` distinct customers - these are excluded as noise.
    Also returns the full per-entity sharer-count series for diagnostics.
    """
    valid = transactions.dropna(subset=[entity_type])
    sharer_counts = valid.groupby(entity_type)["customer_id"].nunique()
    hubs = set(sharer_counts[sharer_counts > max_sharers].index)
    return hubs, sharer_counts


def build_filtered_edges(transactions: pd.DataFrame, entity_types: list, max_sharers: int):
    """
    Same idea as graph_engine.build_graph's edge builder, but skips any
    entity value identified as a hub for its entity type first.
    """
    edge_counts = defaultdict(lambda: {etype: 0 for etype in entity_types})
    hub_summary = {}

    for entity_type in entity_types:
        hubs, sharer_counts = identify_hub_entities(transactions, entity_type, max_sharers)
        hub_summary[entity_type] = {
            "total_distinct_values": int(sharer_counts.shape[0]),
            "num_hubs_removed": len(hubs),
            "max_sharers_seen": int(sharer_counts.max()) if not sharer_counts.empty else 0,
        }

        valid_txns = transactions.dropna(subset=[entity_type])
        valid_txns = valid_txns[~valid_txns[entity_type].isin(hubs)]
        grouped = valid_txns.groupby(entity_type)["customer_id"].apply(lambda s: sorted(set(s)))

        for customers_sharing_entity in grouped:
            if len(customers_sharing_entity) < 2:
                continue
            for customer_a, customer_b in itertools.combinations(customers_sharing_entity, 2):
                edge_counts[(customer_a, customer_b)][entity_type] += 1

    return edge_counts, hub_summary


def build_graph(all_customer_ids: list, edge_counts: dict, min_edge_weight: int) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(all_customer_ids)
    for (customer_a, customer_b), counts in edge_counts.items():
        weight = sum(counts.values())
        if weight >= min_edge_weight:
            graph.add_edge(customer_a, customer_b, weight=weight, **counts)
    return graph


def split_large_components(graph: nx.Graph, max_size: int) -> dict:
    """
    Runs connected components first; any component still larger than
    max_size is further broken up using greedy modularity community
    detection, since a real ring (capped at 25 members by design) shouldn't
    naturally form a much larger connected group after hub removal.
    Returns { customer_id: cluster_id }.
    """
    cluster_assignment = {}
    next_cluster_id = 0

    for component in nx.connected_components(graph):
        if len(component) <= max_size:
            for node in component:
                cluster_assignment[node] = next_cluster_id
            next_cluster_id += 1
            continue

        print(f"   Component of {len(component)} nodes exceeds max size ({max_size}) - "
              f"running community detection to split it further...")
        subgraph = graph.subgraph(component)
        try:
            communities = greedy_modularity_communities(subgraph, weight="weight")
        except Exception as error:
            print(f"   ⚠️  Community detection failed on this component ({error}); "
                  f"keeping it as one cluster")
            communities = [component]

        for community in communities:
            for node in community:
                cluster_assignment[node] = next_cluster_id
            next_cluster_id += 1

    return cluster_assignment


def evaluate_against_ground_truth(customers: pd.DataFrame, cluster_df: pd.DataFrame) -> None:
    print("\nSanity check - does detected clustering match known rings?")
    print("(Diagnostic only - ring_id was never used to build the clusters.)")

    merged = customers.merge(cluster_df, on="customer_id", how="left")
    ring_ids = sorted(merged["ring_id"].dropna().unique())

    for ring_id in ring_ids:
        ring_members = merged[merged["ring_id"] == ring_id]
        cluster_ids = ring_members["cluster_id"].dropna()
        if cluster_ids.empty:
            print(f"   {ring_id}: no members ended up in any cluster")
            continue
        most_common_cluster = cluster_ids.mode().iloc[0]
        matching = (cluster_ids == most_common_cluster).sum()
        pct = matching / len(ring_members) * 100
        cluster_total_size = int((merged["cluster_id"] == most_common_cluster).sum())
        purity = matching / cluster_total_size * 100 if cluster_total_size else 0
        print(f"   {ring_id}: {matching}/{len(ring_members)} members ({pct:.1f}%) grouped into "
              f"cluster {int(most_common_cluster)} (cluster size {cluster_total_size}, "
              f"{purity:.1f}% of that cluster is truly this ring)")


def main():
    print("FraudRing abuse-ring detection")
    print("=" * 50)

    customers = load_csv("customers.csv")
    transactions = load_csv("transactions.csv")

    print("Identifying and removing hub entities (shared by too many unrelated customers)...")
    edge_counts, hub_summary = build_filtered_edges(
        transactions, config.SHARED_ENTITY_TYPES, config.MAX_ENTITY_SHARERS
    )
    for entity_type, summary in hub_summary.items():
        print(f"   {entity_type}: {summary['num_hubs_removed']}/{summary['total_distinct_values']} "
              f"values removed as hubs (max sharers seen: {summary['max_sharers_seen']})")

    print(f"\nBuilding filtered graph (min_edge_weight={config.MIN_EDGE_WEIGHT})...")
    graph = build_graph(list(customers["customer_id"]), edge_counts, config.MIN_EDGE_WEIGHT)
    print(f"Graph has {graph.number_of_nodes():,} nodes and {graph.number_of_edges():,} edges "
          f"(down from 553,688 edges before hub removal)")

    component_sizes = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    non_trivial = [s for s in component_sizes if s > 1]
    print(f"Connected components: {len(component_sizes):,} total, "
          f"{len(non_trivial)} with more than 1 member, "
          f"largest = {component_sizes[0] if component_sizes else 0}")

    print("\nSplitting any oversized components with community detection...")
    cluster_assignment = split_large_components(graph, config.MAX_CLUSTER_SIZE_BEFORE_SPLIT)

    cluster_df = pd.DataFrame([
        {"customer_id": cid, "cluster_id": cluster_id}
        for cid, cluster_id in cluster_assignment.items()
    ])
    cluster_sizes = cluster_df.groupby("cluster_id").size().rename("cluster_size")
    cluster_df = cluster_df.merge(cluster_sizes, on="cluster_id", how="left")

    reportable = cluster_df[cluster_df["cluster_size"] >= config.MIN_CLUSTER_SIZE_TO_REPORT]
    print(f"\n{cluster_df['cluster_id'].nunique():,} total clusters found, "
          f"{reportable['cluster_id'].nunique():,} meet the reporting size threshold "
          f"(>= {config.MIN_CLUSTER_SIZE_TO_REPORT} members)")

    evaluate_against_ground_truth(customers, cluster_df)

    try:
        os.makedirs(config.GRAPH_OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.GRAPH_OUTPUT_DIR, "ring_clusters.csv")
        cluster_df.to_csv(output_path, index=False)
        print(f"\n✅ Cluster assignments saved -> {output_path}")
    except OSError as error:
        print(f"❌ Failed to save cluster assignments: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()