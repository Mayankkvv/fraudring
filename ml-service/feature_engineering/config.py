"""
Configuration for transaction risk feature engineering.
"""

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

# Time-based split ratios. Train comes first chronologically, then val,
# then test - never random, since real fraud systems are always evaluated
# on data that happened AFTER the data they trained on.
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
# TEST_RATIO is whatever remains (~0.15)

# Number of full abuse rings forced entirely into the test set, regardless
# of where their transactions naturally fall in time. This guarantees the
# model is tested on at least a few rings it has never seen in training -
# required by context/DATASET_SPEC.md ("held-out rings").
NUM_HELD_OUT_RINGS = 2