"""
Configuration for abuse-ring detection.

Step 13's raw graph collapsed into one 2,000-node connected component
because entities shared by MANY unrelated customers (a popular coupon used
by hundreds of ordinary customers, a widely-used device) create "hub" edges
that connect the entire customer base together, even though only a handful
of customers are actually coordinating. This step removes those hub
entities before building edges, so remaining connections reflect genuine,
unusually concentrated sharing - the real signature of a coordinated ring.
"""

RAW_DIR = "data/raw"
GRAPH_OUTPUT_DIR = "data/graph"

SHARED_ENTITY_TYPES = ["device_id", "ip_id", "coupon_id"]

# An entity (a specific device_id/ip_id/coupon_id) used by MORE than this
# many distinct customers is treated as a "hub" - a shared public resource,
# not evidence of coordination - and excluded from edge building entirely.
# Real rings are capped at 25 members (data_generation/config.py), so
# anything shared by well beyond that many customers is very unlikely to be
# ring behavior specifically.
MAX_ENTITY_SHARERS = 30

# Minimum total shared-entity weight required to keep an edge after hub
# removal (two customers must share at least this many entities/occurrences).
MIN_EDGE_WEIGHT = 2

# If a connected component (after hub removal) is still larger than this,
# it's further split using community detection instead of being reported
# as one giant ring.
MAX_CLUSTER_SIZE_BEFORE_SPLIT = 60

# Clusters smaller than this (after all filtering) are not reported as
# candidate rings - a size-1 or size-2 "cluster" isn't meaningful evidence.
MIN_CLUSTER_SIZE_TO_REPORT = 3