"""
SHAP explainability for the baseline XGBoost risk model.

Two things this module provides:
1. A global feature importance report (which features matter most overall)
2. explain_transaction(transaction_id) - per-transaction evidence, meant to
   be reused later by the AI investigation agent's get_model_evidence() tool.
   The LLM will call this function (via an API route in a later step) rather
   than guessing why a transaction was flagged.

Run with (from ml-service/, venv active):
    python -m explainability.explain_model                    # global report
    python -m explainability.explain_model --transaction TXN000123   # one transaction
"""

import argparse
import json
import os
import sys

import joblib
import matplotlib
matplotlib.use("Agg")  # no GUI needed - we're saving to a file, not showing a window
import matplotlib.pyplot as plt
import pandas as pd
import shap

from explainability import config

NON_FEATURE_COLS = {"transaction_id", "customer_id", "ring_id", "timestamp", "label", "split"}


def load_model_and_features():
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


def build_explainer(model):
    """TreeExplainer is fast and exact for tree-based models like XGBoost."""
    return shap.TreeExplainer(model)


def generate_global_report(model, explainer, test_df: pd.DataFrame, feature_cols: list):
    """
    Computes mean |SHAP value| per feature across a sample of test
    transactions - this is the model's overall "what matters most" ranking,
    used for the eventual Model Performance dashboard page.
    """
    print("Generating global feature importance report...")

    sample_size = min(config.GLOBAL_SUMMARY_SAMPLE_SIZE, len(test_df))
    sample = test_df.sample(n=sample_size, random_state=42)
    X_sample = sample[feature_cols].fillna(0)

    shap_values = explainer.shap_values(X_sample)

    importance = pd.Series(
        abs(shap_values).mean(axis=0), index=feature_cols
    ).sort_values(ascending=False)

    try:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        # Save as JSON for use in the frontend later
        importance_path = os.path.join(config.OUTPUT_DIR, "global_feature_importance.json")
        with open(importance_path, "w") as f:
            json.dump(importance.round(6).to_dict(), f, indent=2)
        print(f"✅ Feature importance JSON saved -> {importance_path}")

        # Save a simple bar chart image
        plt.figure(figsize=(8, 6))
        top_features = importance.head(15)[::-1]  # reverse for horizontal bar chart order
        plt.barh(top_features.index, top_features.values, color="#4f46e5")
        plt.xlabel("Mean |SHAP value| (average impact on risk score)")
        plt.title("FraudRing - Global Feature Importance (Top 15)")
        plt.tight_layout()
        chart_path = os.path.join(config.OUTPUT_DIR, "global_feature_importance.png")
        plt.savefig(chart_path, dpi=150)
        plt.close()
        print(f"✅ Feature importance chart saved -> {chart_path}")
    except OSError as error:
        print(f"❌ Failed to save explainability outputs: {error}")
        sys.exit(1)

    print("\nTop 10 most important features overall:")
    for feature, value in importance.head(10).items():
        print(f"   {feature}: {value:.4f}")


def explain_transaction(transaction_id: str) -> dict:
    """
    Returns real, model-grounded evidence for why a single transaction got
    its risk score - meant to be called by the AI investigation agent later.
    Never invents evidence: every value here comes directly from the trained
    model's own SHAP attribution for this specific row.

    Returns a dict like:
    {
        "transaction_id": "TXN000123",
        "risk_score": 0.91,
        "top_contributors": [
            {"feature": "customer_refund_count_before", "value": 4,
             "shap_contribution": 0.34, "direction": "increased_risk"},
            ...
        ]
    }
    Returns {"error": "..."} if the transaction isn't found - the caller
    (later, the LLM tool) must surface this rather than fabricate a result.
    """
    model, feature_cols = load_model_and_features()
    test_df = load_test_set()

    row = test_df[test_df["transaction_id"] == transaction_id]
    if row.empty:
        return {"error": f"Transaction {transaction_id} not found in the evaluated test set."}

    X_row = row[feature_cols].fillna(0)
    explainer = build_explainer(model)
    shap_values = explainer.shap_values(X_row)[0]
    risk_score = float(model.predict_proba(X_row)[:, 1][0])

    contributions = pd.Series(shap_values, index=feature_cols).sort_values(
        key=lambda s: s.abs(), ascending=False
    )

    top_contributors = []
    for feature, shap_value in contributions.head(config.TOP_N_FEATURES).items():
        top_contributors.append({
            "feature": feature,
            "value": float(X_row.iloc[0][feature]),
            "shap_contribution": round(float(shap_value), 4),
            "direction": "increased_risk" if shap_value > 0 else "decreased_risk",
        })

    return {
        "transaction_id": transaction_id,
        "risk_score": round(risk_score, 4),
        "top_contributors": top_contributors,
    }


def main():
    parser = argparse.ArgumentParser(description="FraudRing SHAP explainability")
    parser.add_argument(
        "--transaction", type=str, default=None,
        help="Explain a single transaction_id instead of running the global report",
    )
    args = parser.parse_args()

    print("FraudRing explainability")
    print("=" * 50)

    if args.transaction:
        result = explain_transaction(args.transaction)
        print(json.dumps(result, indent=2))
        if "error" in result:
            sys.exit(1)
        return

    model, feature_cols = load_model_and_features()
    test_df = load_test_set()
    explainer = build_explainer(model)
    generate_global_report(model, explainer, test_df, feature_cols)


if __name__ == "__main__":
    main()