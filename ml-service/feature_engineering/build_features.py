"""
Builds the transaction-level risk feature table from the raw synthetic
dataset in data/raw/, and produces a chronological train/val/test split.

Every feature is computed using only information available up to and
including the transaction's own timestamp - no future information leaks
into any row. Two full abuse rings are forced entirely into the test set
so detection is evaluated on rings the model has never seen.

Run with (from ml-service/, venv active):
    python -m feature_engineering.build_features
"""

import os
import sys

import numpy as np
import pandas as pd

from feature_engineering import config


def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(config.RAW_DIR, filename)
    if not os.path.exists(path):
        print(f"❌ Missing required file: {path}")
        print("   Run Step 6's generator first: python -m data_generation.generate_dataset")
        sys.exit(1)
    return pd.read_csv(path)


def load_all_tables() -> dict:
    return {
        "customers": load_csv("customers.csv"),
        "transactions": load_csv("transactions.csv"),
        "coupons": load_csv("coupons.csv"),
        "payment_instruments": load_csv("payment_instruments.csv"),
        "merchant_accounts": load_csv("merchant_accounts.csv"),
        "refunds": load_csv("refunds.csv"),
        "chargebacks": load_csv("chargebacks.csv"),
    }


def count_prior_events_per_customer(txns: pd.DataFrame, events: pd.DataFrame, time_col: str) -> pd.Series:
    """
    For each transaction, counts how many rows in `events` for the SAME
    customer happened strictly before that transaction's timestamp.
    Used for refund/chargeback history without leaking future information.
    `events` must have columns: customer_id, <time_col>.
    """
    result = pd.Series(0, index=txns.index, dtype=int)
    events = events.dropna(subset=["customer_id", time_col]).sort_values(time_col)

    for customer_id, txn_group in txns.groupby("customer_id"):
        customer_event_times = events.loc[events["customer_id"] == customer_id, time_col].values
        if len(customer_event_times) == 0:
            continue
        txn_times = txn_group["timestamp"].values
        # side='left' -> count of event times strictly before each txn time
        counts = np.searchsorted(customer_event_times, txn_times, side="left")
        result.loc[txn_group.index] = counts

    return result


def build_customer_temporal_features(txns: pd.DataFrame) -> pd.DataFrame:
    """Velocity and spending-pattern features, computed without future leakage."""
    grp = txns.groupby("customer_id")

    txns["customer_txn_number"] = grp.cumcount() + 1

    # Expanding mean/std of PAST amounts only (shift excludes the current row)
    txns["customer_avg_amount_before"] = grp["amount"].transform(lambda s: s.shift().expanding().mean())
    txns["customer_std_amount_before"] = grp["amount"].transform(lambda s: s.shift().expanding().std())

    # First transaction for a customer has no history - treat as "not unusual"
    txns["customer_avg_amount_before"] = txns["customer_avg_amount_before"].fillna(txns["amount"])
    txns["customer_std_amount_before"] = txns["customer_std_amount_before"].fillna(0)

    safe_std = txns["customer_std_amount_before"].replace(0, 1)
    txns["amount_zscore"] = (txns["amount"] - txns["customer_avg_amount_before"]) / safe_std

    return txns


def build_refund_chargeback_features(txns: pd.DataFrame, refunds: pd.DataFrame, chargebacks: pd.DataFrame) -> pd.DataFrame:
    txn_customer_map = txns[["transaction_id", "customer_id"]]

    refunds = refunds.copy()
    refunds["requested_at"] = pd.to_datetime(refunds["requested_at"])
    refunds_with_customer = refunds.merge(txn_customer_map, on="transaction_id", how="left")

    chargebacks = chargebacks.copy()
    chargebacks["filed_at"] = pd.to_datetime(chargebacks["filed_at"])
    chargebacks_with_customer = chargebacks.merge(txn_customer_map, on="transaction_id", how="left")

    txns["customer_refund_count_before"] = count_prior_events_per_customer(
        txns, refunds_with_customer, "requested_at"
    )
    txns["customer_chargeback_count_before"] = count_prior_events_per_customer(
        txns, chargebacks_with_customer, "filed_at"
    )
    return txns


def build_coupon_features(txns: pd.DataFrame, coupons: pd.DataFrame) -> pd.DataFrame:
    txns["coupon_used"] = txns["coupon_id"].notna().astype(int)

    txns["coupon_usage_count_before"] = 0
    coupon_mask = txns["coupon_id"].notna()
    txns.loc[coupon_mask, "coupon_usage_count_before"] = (
        txns.loc[coupon_mask].groupby("coupon_id").cumcount()
    )

    txns = txns.merge(coupons[["coupon_id", "max_uses"]], on="coupon_id", how="left")
    txns["coupon_max_uses"] = txns["max_uses"].fillna(-1)  # -1 = not applicable, no coupon used
    txns["coupon_over_limit"] = (
        (txns["coupon_used"] == 1) & (txns["coupon_usage_count_before"] >= txns["coupon_max_uses"])
    ).astype(int)
    txns = txns.drop(columns=["max_uses"])
    return txns


def build_infrastructure_features(txns: pd.DataFrame) -> pd.DataFrame:
    """
    NOTE - simplification: these counts use the FULL dataset, not just
    transactions up to this point in time. In a real streaming system this
    would come from a live-updating graph (built in Step 15). For this
    baseline risk model, dataset-wide sharing counts are a reasonable proxy
    and we're flagging that explicitly rather than pretending otherwise.
    """
    device_counts = txns.groupby("device_id")["customer_id"].nunique().rename("device_distinct_customers")
    txns = txns.merge(device_counts, on="device_id", how="left")

    ip_counts = txns.groupby("ip_id")["customer_id"].nunique().rename("ip_distinct_customers")
    txns = txns.merge(ip_counts, on="ip_id", how="left")

    return txns


def build_customer_and_merchant_features(txns: pd.DataFrame, customers: pd.DataFrame,
                                          instruments: pd.DataFrame, merchants: pd.DataFrame) -> pd.DataFrame:
    customers = customers.copy()
    customers["signup_date"] = pd.to_datetime(customers["signup_date"])
    customers["kyc_verified"] = customers["kyc_verified"].astype(bool).astype(int)

    txns = txns.merge(
        customers[["customer_id", "signup_date", "kyc_verified", "ring_id"]],
        on="customer_id", how="left",
    )
    txns["account_age_days"] = (txns["timestamp"] - txns["signup_date"]).dt.days.clip(lower=0)

    instr_counts = instruments.groupby("customer_id").size().rename("num_payment_instruments")
    txns = txns.merge(instr_counts, on="customer_id", how="left")
    txns["num_payment_instruments"] = txns["num_payment_instruments"].fillna(0).astype(int)

    instr_type = instruments[["instrument_id", "type"]].rename(
        columns={"instrument_id": "payment_instrument_id", "type": "instrument_type"}
    )
    txns = txns.merge(instr_type, on="payment_instrument_id", how="left")

    merchant_risk = merchants[["merchant_id", "risk_tier"]].rename(columns={"risk_tier": "merchant_risk_tier"})
    txns = txns.merge(merchant_risk, on="merchant_id", how="left")

    return txns


def time_based_split(df: pd.DataFrame, train_ratio: float, val_ratio: float, num_held_out_rings: int) -> pd.Series:
    df = df.sort_values("timestamp").reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    split = pd.Series("train", index=df.index)
    split.iloc[train_end:val_end] = "val"
    split.iloc[val_end:] = "test"

    ring_ids_sorted = sorted(r for r in df["ring_id"].dropna().unique())
    held_out_rings = ring_ids_sorted[-num_held_out_rings:] if len(ring_ids_sorted) >= num_held_out_rings else ring_ids_sorted
    if held_out_rings:
        split.loc[df["ring_id"].isin(held_out_rings)] = "test"

    return split, held_out_rings


def main():
    print("FraudRing feature engineering")
    print("=" * 50)

    tables = load_all_tables()
    txns = tables["transactions"].copy()
    txns["timestamp"] = pd.to_datetime(txns["timestamp"])
    txns = txns.sort_values("timestamp").reset_index(drop=True)

    txns["hour_of_day"] = txns["timestamp"].dt.hour
    txns["day_of_week"] = txns["timestamp"].dt.dayofweek

    print("Building customer temporal features...")
    txns = build_customer_temporal_features(txns)

    print("Building refund/chargeback history features...")
    txns = build_refund_chargeback_features(txns, tables["refunds"], tables["chargebacks"])

    print("Building coupon features...")
    txns = build_coupon_features(txns, tables["coupons"])

    print("Building infrastructure sharing features...")
    txns = build_infrastructure_features(txns)

    print("Building customer/merchant features...")
    txns = build_customer_and_merchant_features(
        txns, tables["customers"], tables["payment_instruments"], tables["merchant_accounts"]
    )

    txns = pd.get_dummies(
        txns, columns=["instrument_type", "merchant_risk_tier"],
        prefix=["instrument", "merchant_risk"], dummy_na=False,
    )

    feature_cols = [
        "amount", "hour_of_day", "day_of_week", "account_age_days", "kyc_verified",
        "customer_txn_number", "customer_avg_amount_before", "amount_zscore",
        "customer_refund_count_before", "customer_chargeback_count_before",
        "coupon_used", "coupon_usage_count_before", "coupon_max_uses", "coupon_over_limit",
        "device_distinct_customers", "ip_distinct_customers", "num_payment_instruments",
    ] + [c for c in txns.columns if c.startswith("instrument_") or c.startswith("merchant_risk_")]

    meta_cols = ["transaction_id", "customer_id", "ring_id", "timestamp"]

    final = txns[meta_cols + feature_cols + ["is_ring_transaction"]].copy()
    final = final.rename(columns={"is_ring_transaction": "label"})

    print("\nSplitting into train/val/test (chronological + held-out rings)...")
    final["split"], held_out_rings = time_based_split(
        final, config.TRAIN_RATIO, config.VAL_RATIO, config.NUM_HELD_OUT_RINGS
    )
    print(f"   Held-out rings (test-only): {held_out_rings}")

    try:
        os.makedirs(config.PROCESSED_DIR, exist_ok=True)
        final.to_csv(os.path.join(config.PROCESSED_DIR, "features_full.csv"), index=False)
        for split_name in ["train", "val", "test"]:
            subset = final[final["split"] == split_name]
            subset.to_csv(os.path.join(config.PROCESSED_DIR, f"{split_name}.csv"), index=False)
    except OSError as error:
        print(f"❌ Failed to write processed files: {error}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Summary")
    for split_name in ["train", "val", "test"]:
        subset = final[final["split"] == split_name]
        ring_pct = subset["label"].mean() * 100 if len(subset) else 0
        print(f"   {split_name:5s}: {len(subset):>7,} rows | ring-labeled: {ring_pct:.2f}%")
    print(f"\nFeature columns ({len(feature_cols)}): {feature_cols}")
    print("Done. Files are in:", config.PROCESSED_DIR)


if __name__ == "__main__":
    main()