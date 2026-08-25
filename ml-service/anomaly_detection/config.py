"""
Configuration for behavioral anomaly detection.

IMPORTANT: CONTAMINATION is an ASSUMPTION about what fraction of transactions
are "unusual" - it does not use the real label. It's set close to (but not
exactly equal to) the known ring transaction rate purely as a reasonable
starting guess for an unsupervised model, and is clearly documented as such.
"""

PROCESSED_DIR = "data/processed"
MODEL_PATH = "models/isolation_forest.joblib"

RANDOM_SEED = 42
N_ESTIMATORS = 200

# ASSUMED proportion of transactions expected to be anomalous. In a real
# deployment this would be tuned against alert-volume capacity, not guessed.
CONTAMINATION = 0.08

# Only genuinely behavioral/temporal features go into anomaly detection -
# categorical one-hot columns (instrument type, merchant risk tier) are
# excluded because Isolation Forest works on continuous numeric spread,
# not category membership.
FEATURES_FOR_ANOMALY = [
    "amount",
    "hour_of_day",
    "day_of_week",
    "account_age_days",
    "customer_txn_number",
    "customer_avg_amount_before",
    "amount_zscore",
    "customer_refund_count_before",
    "customer_chargeback_count_before",
    "coupon_usage_count_before",
    "device_distinct_customers",
    "ip_distinct_customers",
]