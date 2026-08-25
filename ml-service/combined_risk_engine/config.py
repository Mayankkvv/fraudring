"""
Configuration for the combined risk engine.

IMPORTANT: The three signal weights below are a REASONABLE STARTING
ASSUMPTION, not the result of formal optimization (e.g. grid search against
val.csv). They are chosen so the ML model - our best-validated single
signal - dominates, while anomaly and graph signals nudge the score rather
than overriding it. This should be revisited once Step 17's decision engine
does proper cost-based tuning.
"""

PROCESSED_DIR = "data/processed"
GRAPH_DIR = "data/graph"
MODEL_PATH = "models/xgboost_baseline.joblib"
BASELINE_TEST_METRICS_PATH = "models/test_metrics.json"
OUTPUT_METRICS_PATH = "models/combined_risk_test_metrics.json"

# ASSUMED signal weights (must sum to 1.0).
WEIGHT_ML = 0.5
WEIGHT_ANOMALY = 0.2
WEIGHT_GRAPH = 0.3

# Threshold used to convert combined_risk_score into a positive/negative
# classification for precision/recall/F1 - kept identical to the baseline
# model's threshold (Step 9/10) so the two are directly comparable.
CLASSIFICATION_THRESHOLD = 0.5

# Bounded action thresholds. Below LOW -> ALLOW, between LOW and HIGH ->
# STEP_UP_VERIFICATION, at or above HIGH -> BLOCK. These are placeholder
# thresholds, not derived from a cost model yet - Step 17 replaces this
# with a proper expected-loss-based decision policy.
DECISION_LOW_THRESHOLD = 0.3
DECISION_HIGH_THRESHOLD = 0.7

# Simplification: the graph signal is currently BINARY - 1.0 if the
# customer belongs to a cluster at or above the reporting size threshold
# (see abuse_ring_detection/config.py's MIN_CLUSTER_SIZE_TO_REPORT), else
# 0.0. A more graded graph risk score (e.g. weighted by cluster density)
# could replace this later, but a clear binary signal is easier to reason
# about and audit for a first version.