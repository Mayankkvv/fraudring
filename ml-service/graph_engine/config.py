"""
Configuration for entity relationship graph construction.
"""

RAW_DIR = "data/raw"
GRAPH_OUTPUT_DIR = "data/graph"

# Which shared entity types connect two customers in the projected graph.
# Two customers get an edge if they show up on the SAME transaction-linked
# device_id, ip_id, or coupon_id at least once.
SHARED_ENTITY_TYPES = ["device_id", "ip_id", "coupon_id"]