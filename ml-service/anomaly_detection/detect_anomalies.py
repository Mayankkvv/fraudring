"""
Behavioral anomaly detection using Isolation Forest - unsupervised, so it
never sees the ring_id/label ground truth during fitting. Fit only on
train.csv to avoid any leakage, then applied consistently to val/test.

Adds an `anomaly_score` column (0 = looks normal, 1 = highly anomalous) to
train.csv, val.csv, and test.csv in data/processed/, so it's available as
an extra signal for the combined risk engine in a later step.

Run with (from ml-service/, venv active):
    python -m anomaly_detection.detect_anomalies
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

from anomaly_detection import config


def load_split(name: str) -> pd.DataFrame:
    path = os.path.join(config.PROCESSED_DIR, f"{name}.csv")
    if not os.path.exists(path):
        print(f"❌ Missing {path}")
        print("   Run Step 8 first: python -m feature_engineering.build_features")
        sys.exit(1)
    return pd.read_csv(path)


def save_split(df: pd.DataFrame, name: str) -> None:
    path = os.path.join(config.PROCESSED_DIR, f"{name}.csv")
    df.to_csv(path, index=False)
    print(f"✅ Updated {path} with anomaly_score column")


def scale_scores(raw_scores: np.ndarray, train_min: float, train_max: float) -> np.ndarray:
    """
    Rescales raw Isolation Forest scores to a 0-1 range using train-set
    min/max, so anomaly_score is easy to read and compare across splits.
    Values from val/test can technically fall slightly outside [0, 1] if
    they're more extreme than anything seen in train - that's expected and
    informative, so we clip only for display purposes, not for the raw value.
    """
    if train_max == train_min:
        return np.zeros_like(raw_scores)
    scaled = (raw_scores - train_min) / (train_max - train_min)
    return scaled


def main():
    print("FraudRing behavioral anomaly detection")
    print("=" * 50)

    train_df = load_split("train")
    val_df = load_split("val")
    test_df = load_split("test")

    missing_cols = [c for c in config.FEATURES_FOR_ANOMALY if c not in train_df.columns]
    if missing_cols:
        print(f"❌ Missing expected feature columns: {missing_cols}")
        print("   Check feature_engineering/build_features.py output matches anomaly_detection/config.py")
        sys.exit(1)

    X_train = train_df[config.FEATURES_FOR_ANOMALY].fillna(0)
    X_val = val_df[config.FEATURES_FOR_ANOMALY].fillna(0)
    X_test = test_df[config.FEATURES_FOR_ANOMALY].fillna(0)

    print(f"Training Isolation Forest on {len(X_train):,} transactions "
          f"(contamination assumption={config.CONTAMINATION})...")
    model = IsolationForest(
        n_estimators=config.N_ESTIMATORS,
        contamination=config.CONTAMINATION,
        random_state=config.RANDOM_SEED,
        n_jobs=-1,
    )
    model.fit(X_train)

    # sklearn's score_samples: HIGHER = more normal. We flip the sign so that
    # HIGHER anomaly_score = MORE anomalous, which is more intuitive downstream.
    raw_train_scores = -model.score_samples(X_train)
    raw_val_scores = -model.score_samples(X_val)
    raw_test_scores = -model.score_samples(X_test)

    train_min, train_max = raw_train_scores.min(), raw_train_scores.max()

    train_df["anomaly_score"] = scale_scores(raw_train_scores, train_min, train_max).round(4)
    val_df["anomaly_score"] = scale_scores(raw_val_scores, train_min, train_max).round(4)
    test_df["anomaly_score"] = scale_scores(raw_test_scores, train_min, train_max).round(4)

    print("\nSanity check - does anomaly_score correlate with the REAL label at all?")
    print("(This is diagnostic only - the model never saw labels during fitting.)")
    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        if df["label"].nunique() < 2:
            print(f"   {name}: skipped (only one class present)")
            continue
        auc = roc_auc_score(df["label"], df["anomaly_score"])
        print(f"   {name}: anomaly_score vs. true label ROC-AUC = {auc:.4f}")

    save_split(train_df, "train")
    save_split(val_df, "val")
    save_split(test_df, "test")

    try:
        os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
        joblib.dump({
            "model": model,
            "features": config.FEATURES_FOR_ANOMALY,
            "train_min": float(train_min),
            "train_max": float(train_max),
        }, config.MODEL_PATH)
        print(f"\n✅ Isolation Forest model saved -> {config.MODEL_PATH}")
    except OSError as error:
        print(f"❌ Failed to save model: {error}")
        sys.exit(1)

    print("\nTop 5 most anomalous transactions overall (test set):")
    top5 = test_df.sort_values("anomaly_score", ascending=False).head(5)
    for _, row in top5.iterrows():
        print(f"   {row['transaction_id']}: anomaly_score={row['anomaly_score']}, "
              f"true_label={bool(row['label'])}")


if __name__ == "__main__":
    main()