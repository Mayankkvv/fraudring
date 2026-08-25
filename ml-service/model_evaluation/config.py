"""
Configuration for test-set evaluation and financial exposure estimates.

IMPORTANT: AVG_FALSE_POSITIVE_COST is an ASSUMPTION, not a measured number -
it represents the estimated operational/friction cost of putting one
legitimate customer through step-up verification unnecessarily (support
load, cart abandonment risk, etc). It is clearly labeled as an assumption
everywhere it's reported, and should be replaced with a real figure if
Razorpay or the buildathon judges provide one.
"""

MODEL_PATH = "models/xgboost_baseline.joblib"
TEST_PATH = "data/processed/test.csv"
OUTPUT_PATH = "models/test_metrics.json"

CURRENCY_SYMBOL = "₹"

# ASSUMED unit cost of one false positive (unnecessary step-up verification).
AVG_FALSE_POSITIVE_COST = 40.0

# A ring is considered "detected" at the ring level if at least this
# fraction of its transactions get flagged by the model.
RING_DETECTION_THRESHOLD = 0.5