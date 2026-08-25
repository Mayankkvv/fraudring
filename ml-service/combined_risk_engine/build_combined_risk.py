"""
Combines the ML risk score, behavioral anomaly score, and graph/ring
cluster membership into one combined_risk_score per transaction, plus a
bounded decision (ALLOW / STEP_UP_VERIFICATION / BLOCK).

Also evaluates the combined score against the baseline ML-only score on
the same held-out test set, to honestly check whether combining signals
actually improves detection - not just assume it does.

Run with (from ml-service/, venv active):
    python -m combined_risk_engine.build_combined_risk
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

from combined_risk_engine import config
from abuse_ring_detection import config as ring_config

NON_FEATURE_COLS = {
    "transaction_id", "customer_id", "ring_id", "timestamp", "label", "split",
    "anomaly_score",
}


def load_model_and_features():
    if not os.path.exists(config.MODEL_PATH):
        print(f"❌ Missing model file: {config.MODEL_PATH}")
        print("   Run Step 9 first: python -m model_training.train_model")
        sys.exit(1)
    bundle = joblib.load(config.MODEL_PATH)
    return bundle["model"], bundle["feature_cols"]


def load_split(name: str) -> pd.DataFrame:
    path = os.path.join(config.PROCESSED_DIR, f"{name}.csv")
    if not os.path.exists(path):
        print(f"❌ Missing {path}")
        print("   Run Steps 8 and 12 first (feature engineering, then anomaly detection)")
        sys.exit(1)
    df = pd.read_csv(path)
    if "anomaly_score" not in df.columns:
        print(f"❌ {path} has no anomaly_score column")
        print("   Run Step 12 first: python -m anomaly_detection.detect_anomalies")
        sys.exit(1)
    return df


def load_ring_clusters() -> pd.DataFrame:
    path = os.path.join(config.GRAPH_DIR, "ring_clusters.csv")
    if not os.path.exists(path):
        print(f"❌ Missing {path}")
        print("   Run Step 14 first: python -m abuse_ring_detection.detect_rings")
        sys.exit(1)
    return pd.read_csv(path)


def compute_graph_risk_scores(df: pd.DataFrame, ring_clusters: pd.DataFrame) -> pd.Series:
    """
    Binary graph risk signal: 1.0 if the customer belongs to a cluster at
    or above the reporting size threshold, else 0.0. Customers absent from
    ring_clusters.csv entirely (shouldn't normally happen) default to 0.0.
    """
    merged = df[["customer_id"]].merge(ring_clusters, on="customer_id", how="left")
    merged["cluster_size"] = merged["cluster_size"].fillna(0)
    is_flagged = (merged["cluster_size"] >= ring_config.MIN_CLUSTER_SIZE_TO_REPORT).astype(float)
    return is_flagged.reset_index(drop=True)


def compute_decision(score: float) -> str:
    if score >= config.DECISION_HIGH_THRESHOLD:
        return "BLOCK"
    if score >= config.DECISION_LOW_THRESHOLD:
        return "STEP_UP_VERIFICATION"
    return "ALLOW"


def build_combined_scores(df: pd.DataFrame, model, feature_cols: list, ring_clusters: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    X = df[feature_cols].fillna(0)
    df["ml_risk_score"] = model.predict_proba(X)[:, 1]

    # anomaly_score can slightly exceed 1.0 for extreme outliers (documented
    # in Step 12) - clip here since it's being combined as a 0-1 weight component.
    df["anomaly_score_clipped"] = df["anomaly_score"].clip(0, 1)

    df["graph_risk_score"] = compute_graph_risk_scores(df, ring_clusters)

    df["combined_risk_score"] = (
        config.WEIGHT_ML * df["ml_risk_score"]
        + config.WEIGHT_ANOMALY * df["anomaly_score_clipped"]
        + config.WEIGHT_GRAPH * df["graph_risk_score"]
    ).round(4)

    df["decision"] = df["combined_risk_score"].apply(compute_decision)

    return df


def evaluate(y_true, y_pred, y_proba) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "pr_auc": round(average_precision_score(y_true, y_proba), 4),
        "false_positive_rate": round(fpr, 4),
    }


def print_comparison(baseline_metrics: dict, combined_metrics: dict) -> None:
    print("\nBaseline ML-only vs. Combined Risk Score (test set):")
    print(f"   {'metric':<20} {'ML-only':>10} {'Combined':>10}")
    for key in ["precision", "recall", "f1", "pr_auc", "false_positive_rate"]:
        baseline_val = baseline_metrics.get(key, "n/a")
        combined_val = combined_metrics.get(key, "n/a")
        print(f"   {key:<20} {baseline_val!s:>10} {combined_val!s:>10}")


def main():
    print("FraudRing combined risk engine")
    print("=" * 50)

    weight_sum = config.WEIGHT_ML + config.WEIGHT_ANOMALY + config.WEIGHT_GRAPH
    if abs(weight_sum - 1.0) > 1e-6:
        print(f"❌ Signal weights must sum to 1.0, got {weight_sum}")
        sys.exit(1)

    model, feature_cols = load_model_and_features()
    ring_clusters = load_ring_clusters()

    results = {}
    for split_name in ["train", "val", "test"]:
        print(f"\nProcessing {split_name}.csv...")
        df = load_split(split_name)
        combined_df = build_combined_scores(df, model, feature_cols, ring_clusters)

        out_path = os.path.join(config.PROCESSED_DIR, f"{split_name}_combined.csv")
        combined_df.to_csv(out_path, index=False)
        print(f"✅ Saved -> {out_path}")

        decision_counts = combined_df["decision"].value_counts().to_dict()
        print(f"   Decision breakdown: {decision_counts}")

        results[split_name] = combined_df

    print("\n" + "=" * 50)
    print("Evaluating combined score on TEST set (never used in training)...")
    test_df = results["test"]
    y_true = test_df["label"].astype(int)
    y_proba = test_df["combined_risk_score"]
    y_pred = (y_proba >= config.CLASSIFICATION_THRESHOLD).astype(int)
    combined_metrics = evaluate(y_true, y_pred, y_proba)

    print("\nCombined risk score metrics (test set):")
    for key, value in combined_metrics.items():
        print(f"   {key}: {value}")

    if os.path.exists(config.BASELINE_TEST_METRICS_PATH):
        with open(config.BASELINE_TEST_METRICS_PATH) as f:
            baseline_report = json.load(f)
        baseline_metrics = baseline_report.get("classification_metrics", {})
        print_comparison(baseline_metrics, combined_metrics)
    else:
        print("\n⚠️  No baseline test_metrics.json found (Step 10) - skipping comparison")
        baseline_metrics = {}

    output_report = {
        "weights": {
            "ml": config.WEIGHT_ML,
            "anomaly": config.WEIGHT_ANOMALY,
            "graph": config.WEIGHT_GRAPH,
        },
        "classification_threshold": config.CLASSIFICATION_THRESHOLD,
        "decision_thresholds": {
            "low": config.DECISION_LOW_THRESHOLD,
            "high": config.DECISION_HIGH_THRESHOLD,
        },
        "baseline_ml_only_metrics": baseline_metrics,
        "combined_metrics": combined_metrics,
    }

    try:
        with open(config.OUTPUT_METRICS_PATH, "w") as f:
            json.dump(output_report, f, indent=2)
        print(f"\n✅ Comparison report saved -> {config.OUTPUT_METRICS_PATH}")
    except OSError as error:
        print(f"❌ Failed to save report: {error}")
        sys.exit(1)

    if combined_metrics.get("recall", 0) < baseline_metrics.get("recall", 0):
        print("\n⚠️  Combined recall is LOWER than ML-only recall. That's a real, honest")
        print("   result - it may mean the weights need rebalancing, not that the graph")
        print("   or anomaly signals are useless. Worth discussing before Step 16.")


if __name__ == "__main__":
    main()