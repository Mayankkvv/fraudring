"""
Configuration for SHAP-based model explainability.
"""

MODEL_PATH = "models/xgboost_baseline.joblib"
TEST_PATH = "data/processed/test.csv"
OUTPUT_DIR = "models/explainability"

# Number of top contributing features to report per transaction explanation.
TOP_N_FEATURES = 5

# Max rows sampled for the GLOBAL importance chart (speed - global summary
# doesn't need every row, just a representative sample).
GLOBAL_SUMMARY_SAMPLE_SIZE = 2000