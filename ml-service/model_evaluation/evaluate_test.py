"""
Evaluates the trained baseline model on the held-out test set, including
the abuse rings that were forced entirely into test in Step 8 and never
seen during training in any form.

Reports: precision, recall, F1, PR-AUC, false-positive rate, false-positive
cost, false-negative cost (actual missed fraud amount), estimated prevented
loss, and ring-level detection rates. All numbers come directly from the
model's real predictions - nothing here is invented or adjusted after the
fact to look better.

Run with (from ml-service/, venv active):
    python -m model_evaluation.evaluate_test
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

from model_evaluation import config

NON_FEATURE_COLS = {"transaction_id", "customer_id", "ring_id", "timestamp", "label", "split"}


def load_model():
    if not os.path.exists(config.MODEL_PATH):
        print(f"❌ Missing model file: {config.MODEL_PATH}")
        print("   Run Step 9 first: python -m model_training.train_model")
        sys.exit(1)
    bundle = joblib.load(config.MODEL_PATH)
    return bundle["model"], bundle["feature_cols"]


def load_test_set() -> pd.DataFrame:
    if not os.path.exists(config.TEST_PATH):
        print(f"❌ Missing test set: {config.TEST_PATH}")
        print("   Run Step 8 first: python -m feature_engineering.build_features")
        sys.exit(1)
    return pd.read_csv(config.TEST_PATH)


def get_decision_threshold() -> float:
    """Reuses the threshold chosen in Step 9 so val and test are evaluated consistently."""
    metrics_path = os.path.join("models", "baseline_val_metrics.json")
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            return json.load(f).get("threshold", 0.5)
    print("⚠️  Could not find baseline_val_metrics.json, defaulting threshold to 0.5")
    return 0.5


def compute_classification_metrics(y_true, y_pred, y_proba) -> dict:
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


def compute_financial_metrics(test_df: pd.DataFrame, y_pred) -> dict:
    df = test_df.copy()
    df["predicted"] = y_pred

    total_exposure = round(df.loc[df["label"] == 1, "amount"].sum(), 2)

    true_positive_amount = df.loc[(df["label"] == 1) & (df["predicted"] == 1), "amount"].sum()
    false_negative_amount = df.loc[(df["label"] == 1) & (df["predicted"] == 0), "amount"].sum()
    num_false_positives = int(((df["label"] == 0) & (df["predicted"] == 1)).sum())
    false_positive_cost = round(num_false_positives * config.AVG_FALSE_POSITIVE_COST, 2)

    return {
        "total_fraud_exposure": total_exposure,
        "estimated_prevented_loss": round(true_positive_amount, 2),
        "false_negative_cost_missed_fraud_amount": round(false_negative_amount, 2),
        "false_positive_cost_assumed": false_positive_cost,
        "false_positive_unit_cost_assumption": config.AVG_FALSE_POSITIVE_COST,
        "net_estimated_benefit": round(true_positive_amount - false_positive_cost, 2),
    }


def compute_ring_level_detection(test_df: pd.DataFrame, y_pred) -> dict:
    df = test_df.copy()
    df["predicted"] = y_pred
    ring_report = {}

    ring_ids = sorted(df["ring_id"].dropna().unique())
    for ring_id in ring_ids:
        ring_txns = df[df["ring_id"] == ring_id]
        flagged_pct = ring_txns["predicted"].mean() if len(ring_txns) else 0.0
        detected = flagged_pct >= config.RING_DETECTION_THRESHOLD
        ring_report[ring_id] = {
            "num_transactions": int(len(ring_txns)),
            "pct_flagged": round(flagged_pct * 100, 2),
            "ring_detected": bool(detected),
        }
    return ring_report


def main():
    print("FraudRing test-set evaluation")
    print("=" * 50)

    model, feature_cols = load_model()
    test_df = load_test_set()
    threshold = get_decision_threshold()

    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df["label"].astype(int)

    print(f"Evaluating on {len(test_df):,} held-out test transactions (threshold={threshold})...")
    y_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= threshold).astype(int)

    classification_metrics = compute_classification_metrics(y_test, y_pred, y_proba)
    financial_metrics = compute_financial_metrics(test_df, y_pred)
    ring_report = compute_ring_level_detection(test_df, y_pred)

    print("\n" + "=" * 50)
    print("Classification metrics (test set):")
    for key, value in classification_metrics.items():
        print(f"   {key}: {value}")

    print("\nFinancial metrics (assumptions clearly marked):")
    for key, value in financial_metrics.items():
        print(f"   {key}: {value}")

    print("\nRing-level detection (held-out rings never seen in training):")
    for ring_id, info in ring_report.items():
        status = "✅ DETECTED" if info["ring_detected"] else "❌ MISSED"
        print(f"   {ring_id}: {info['num_transactions']} txns, "
              f"{info['pct_flagged']}% flagged -> {status}")

    report = {
        "threshold_used": threshold,
        "classification_metrics": classification_metrics,
        "financial_metrics": financial_metrics,
        "ring_level_detection": ring_report,
    }

    try:
        os.makedirs(os.path.dirname(config.OUTPUT_PATH), exist_ok=True)
        with open(config.OUTPUT_PATH, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n✅ Full report saved -> {config.OUTPUT_PATH}")
    except OSError as error:
        print(f"❌ Failed to save report: {error}")
        sys.exit(1)

    if not all(info["ring_detected"] for info in ring_report.values()):
        print("\n⚠️  Not every held-out ring was detected at the transaction level.")
        print("   This is expected and honest at this stage - the graph engine (Step 15)")
        print("   is specifically designed to catch what individual-transaction scoring misses.")


if __name__ == "__main__":
    main()