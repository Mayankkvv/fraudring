"""
Central configuration for the synthetic FraudRing dataset generator.
Change these numbers to scale the dataset up or down. Everything else
in data_generation/ reads its settings from here, so this is the one
file you touch to resize the dataset.
"""

# Fixed seed so the "random" dataset is identical every time we run this
# script - important for reproducibility and for comparing model results
# across runs.
RANDOM_SEED = 42

# Entity counts (start small for fast local testing, scale up later for the real demo)
NUM_CUSTOMERS = 2000
NUM_MERCHANTS = 50
NUM_DEVICES = 900          # fewer than customers so devices naturally get reused
NUM_IP_ADDRESSES = 500
NUM_COUPONS = 40

# Abuse ring settings
NUM_RINGS = 8
RING_SIZE_MIN = 8
RING_SIZE_MAX = 25
RING_SHARED_DEVICES = 4     # each ring reuses this many devices among its members
RING_SHARED_IPS = 3         # each ring reuses this many IPs among its members

# Transaction volume
AVG_TRANSACTIONS_PER_CUSTOMER = 10   # normal customers
RING_TRANSACTION_MULTIPLIER = 2.5    # ring members transact more often (velocity signal)

# Date range for the whole dataset
START_DATE = "2025-01-01"
END_DATE = "2026-06-30"

# Output location (relative to where generate_dataset.py is run from)
OUTPUT_DIR = "data/raw"