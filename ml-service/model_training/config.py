"""
Configuration for baseline model training.
"""

PROCESSED_DIR = "data/processed"
MODEL_DIR = "models"

RANDOM_SEED = 42

# XGBoost hyperparameters - deliberately modest for a fast, honest baseline.
# We'll tune these later once graph and anomaly features exist too.
N_ESTIMATORS = 200
MAX_DEPTH = 5
LEARNING_RATE = 0.1

# Probability threshold above which a transaction is classified as "ring".
# 0.5 is a neutral starting point - the real decision engine (a later step)
# will use a cost-based threshold instead of a fixed 0.5.
DECISION_THRESHOLD = 0.5