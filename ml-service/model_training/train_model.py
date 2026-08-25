"""
Trains a baseline XGBoost risk model on the engineered features from Step 8,
and evaluates it honestly on the held-out validation set. Saves the trained
model and its metrics to disk - metrics are never edited or cherry-picked,
whatever the model actually scores is what gets reported.

Run with (from ml-service/, venv active):
    python -m model_training.train_model
"""

import json
import os
import sys

import joblib
import pandas as pd
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, confusion_matrix,
)
from xgboost import XGBClassifier

from model_training import config

# Columns that are metadata/labels, not features fed into the model.
# ring_id in particular must NEVER be used as a feature - that would be
# leaking the ground truth we're trying to predict directly into the model.
NON_FEATURE_COLS = {"transaction_id", "customer_id", "ring_id", "timestamp", "label", "split"}


def load_split(name: str) -> pd.DataFrame:
    path = os.path.join(config.PROCESSED_DIR, f"{name}.csv")
    if not os.path.exists(path):
        print(f"❌ Missing {path}")
        print("   Run Step 8 first: python -m feature_engineering.build_features")
        sys.exit(1)
    return pd.read_csv(path)


def get_feature_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def prepare_xy(df: pd.DataFrame, feature_cols: list):
    X = df[feature_cols].fillna(0)
    y = df["label"].astype(int)
    return X, y


def evaluate(y_true, y_pred, y_proba) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "pr_auc": round(average_precision_score(y_true, y_proba), 4),
        "false_positive_rate": round(fpr, 4),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
    }


def main():
    print("FraudRing baseline model training")
    print("=" * 50)

    train_df = load_split("train")
    val_df = load_split("val")

    feature_cols = get_feature_columns(train_df)
    print(f"Using {len(feature_cols)} features")

    X_train, y_train = prepare_xy(train_df, feature_cols)
    X_val, y_val = prepare_xy(val_df, feature_cols)

    num_negative = int((y_train == 0).sum())
    num_positive = int((y_train == 1).sum())
    if num_positive == 0:
        print("❌ No positive (ring) examples in the training set - cannot train a classifier.")
        print("   Check Step 6/7 output - the ring signal may not be reaching train.csv.")
        sys.exit(1)

    scale_pos_weight = num_negative / num_positive
    print(f"Train class balance: {num_negative:,} negative / {num_positive:,} positive "
          f"(scale_pos_weight={scale_pos_weight:.2f})")

    model = XGBClassifier(
        n_estimators=config.N_ESTIMATORS,
        max_depth=config.MAX_DEPTH,
        learning_rate=config.LEARNING_RATE,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=config.RANDOM_SEED,
        n_jobs=-1,
    )

    print("\nTraining XGBoost model...")
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    print("Evaluating on validation set (never seen during training)...")
    val_proba = model.predict_proba(X_val)[:, 1]
    val_pred = (val_proba >= config.DECISION_THRESHOLD).astype(int)
    metrics = evaluate(y_val, val_pred, val_proba)

    print("\n" + "=" * 50)
    print(f"Validation metrics (threshold={config.DECISION_THRESHOLD}):")
    for key, value in metrics.items():
        print(f"   {key}: {value}")

    try:
        os.makedirs(config.MODEL_DIR, exist_ok=True)
        model_path = os.path.join(config.MODEL_DIR, "xgboost_baseline.joblib")
        joblib.dump({"model": model, "feature_cols": feature_cols}, model_path)
        print(f"\n✅ Model saved -> {model_path}")

        metrics_path = os.path.join(config.MODEL_DIR, "baseline_val_metrics.json")
        with open(metrics_path, "w") as f:
            json.dump({
                "threshold": config.DECISION_THRESHOLD,
                "scale_pos_weight": round(scale_pos_weight, 4),
                "metrics": metrics,
            }, f, indent=2)
        print(f"✅ Metrics saved -> {metrics_path}")
    except OSError as error:
        print(f"❌ Failed to save model/metrics: {error}")
        sys.exit(1)

    if metrics["recall"] < 0.5:
        print("\n⚠️  Recall is below 50% - the baseline is missing more than half of the "
              "ring transactions. That's a real, honest result at this stage - graph and "
              "anomaly signals in later steps should improve it. We will not hide this.")


if __name__ == "__main__":
    main()