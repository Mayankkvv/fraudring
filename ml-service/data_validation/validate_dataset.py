"""
Validates the synthetic FraudRing dataset in data/raw/ before any ML model
is built on top of it. Checks referential integrity, class balance, and
whether the abuse-ring ground truth actually produced a detectable signal.
Every failure or warning is printed explicitly - a validation script that
hides problems is worse than having no validation at all.

Run with (from ml-service/, venv active):
    python -m data_validation.validate_dataset
"""

import os
import sys
import pandas as pd

DATA_DIR = "data/raw"

REQUIRED_FILES = [
    "addresses.csv", "devices.csv", "ip_addresses.csv", "coupons.csv",
    "merchant_accounts.csv", "customers.csv", "payment_instruments.csv",
    "transactions.csv", "payment_attempts.csv", "refunds.csv", "chargebacks.csv",
]


def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


def check_files_exist():
    print("Checking required files exist...")
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(DATA_DIR, f))]
    if missing:
        print(f"❌ Missing files: {missing}")
        return False
    print("✅ All 11 required CSV files found")
    return True


def check_referential_integrity(tables):
    print("\nChecking referential integrity...")
    errors = []

    customer_ids = set(tables["customers"]["customer_id"])
    address_ids = set(tables["addresses"]["address_id"])
    device_ids = set(tables["devices"]["device_id"])
    ip_ids = set(tables["ip_addresses"]["ip_id"])
    instrument_ids = set(tables["payment_instruments"]["instrument_id"])
    coupon_ids = set(tables["coupons"]["coupon_id"])
    merchant_ids = set(tables["merchant_accounts"]["merchant_id"])
    transaction_ids = set(tables["transactions"]["transaction_id"])

    bad = tables["customers"][~tables["customers"]["address_id"].isin(address_ids)]
    if len(bad) > 0:
        errors.append(f"{len(bad)} customers reference a non-existent address_id")

    bad = tables["payment_instruments"][~tables["payment_instruments"]["customer_id"].isin(customer_ids)]
    if len(bad) > 0:
        errors.append(f"{len(bad)} payment_instruments reference a non-existent customer_id")

    txns = tables["transactions"]
    checks = [
        ("customer_id", customer_ids, "customers"),
        ("merchant_id", merchant_ids, "merchant_accounts"),
        ("device_id", device_ids, "devices"),
        ("ip_id", ip_ids, "ip_addresses"),
        ("payment_instrument_id", instrument_ids, "payment_instruments"),
    ]
    for column, valid_ids, target in checks:
        bad = txns[~txns[column].isin(valid_ids)]
        if len(bad) > 0:
            errors.append(f"{len(bad)} transactions reference a non-existent {column} (not in {target})")

    coupon_txns = txns[txns["coupon_id"].notna()]
    bad = coupon_txns[~coupon_txns["coupon_id"].isin(coupon_ids)]
    if len(bad) > 0:
        errors.append(f"{len(bad)} transactions reference a non-existent coupon_id")

    for name in ["refunds", "chargebacks"]:
        bad = tables[name][~tables[name]["transaction_id"].isin(transaction_ids)]
        if len(bad) > 0:
            errors.append(f"{len(bad)} {name} reference a non-existent transaction_id")

    if errors:
        print("❌ Referential integrity issues found:")
        for e in errors:
            print(f"   - {e}")
        return False

    print("✅ All foreign keys resolve correctly")
    return True


def check_class_balance(customers, transactions):
    print("\nChecking ring/class balance...")
    total_customers = len(customers)
    ring_customers = customers["ring_id"].notna().sum()
    ring_pct = ring_customers / total_customers * 100 if total_customers else 0

    total_txns = len(transactions)
    ring_txns = transactions["is_ring_transaction"].sum()
    ring_txn_pct = ring_txns / total_txns * 100 if total_txns else 0

    print(f"   Customers in rings: {ring_customers:,} / {total_customers:,} ({ring_pct:.2f}%)")
    print(f"   Ring transactions:  {ring_txns:,} / {total_txns:,} ({ring_txn_pct:.2f}%)")

    warnings = []
    if ring_pct == 0:
        warnings.append("0% of customers are in a ring - ground truth generation failed")
    elif ring_pct > 40:
        warnings.append(f"{ring_pct:.1f}% of customers are in a ring - unrealistically high, may make detection trivially easy")
    elif ring_pct < 1:
        warnings.append(f"Only {ring_pct:.2f}% of customers are in a ring - may be too few examples to learn from")

    if warnings:
        print("⚠️  Class balance warnings:")
        for w in warnings:
            print(f"   - {w}")
    else:
        print("✅ Ring class balance looks reasonable for a fraud-detection dataset")

    return len(warnings) == 0


def check_ring_signal_strength(customers, transactions):
    """
    Confirms rings actually left a detectable signature: ring members should
    reuse a much smaller pool of devices/IPs per member than 1-per-member.
    If this fails, the graph engine we build later will have nothing to find.
    """
    print("\nChecking abuse-ring signal strength...")
    ring_ids = customers["ring_id"].dropna().unique()

    if len(ring_ids) == 0:
        print("❌ No rings found - cannot check signal strength")
        return False

    issues = []
    for ring_id in ring_ids:
        ring_customer_ids = set(customers[customers["ring_id"] == ring_id]["customer_id"])
        ring_txns = transactions[transactions["customer_id"].isin(ring_customer_ids)]

        if len(ring_txns) == 0:
            issues.append(f"{ring_id} has no transactions at all")
            continue

        num_members = len(ring_customer_ids)
        num_devices_used = ring_txns["device_id"].nunique()
        num_ips_used = ring_txns["ip_id"].nunique()
        devices_per_member = num_devices_used / num_members

        print(f"   {ring_id}: {num_members} members, {num_devices_used} distinct devices, "
              f"{num_ips_used} distinct IPs ({devices_per_member:.2f} devices/member)")

        if devices_per_member > 0.8:
            issues.append(f"{ring_id} members aren't meaningfully sharing devices "
                           f"({devices_per_member:.2f} devices per member - too close to 1:1)")

    if issues:
        print("⚠️  Ring signal issues:")
        for i in issues:
            print(f"   - {i}")
    else:
        print("✅ All rings show meaningful shared-infrastructure signal")

    return len(issues) == 0


def main():
    print("FraudRing dataset validation")
    print("=" * 50)

    if not check_files_exist():
        sys.exit(1)

    tables = {
        "addresses": load_csv("addresses.csv"),
        "devices": load_csv("devices.csv"),
        "ip_addresses": load_csv("ip_addresses.csv"),
        "coupons": load_csv("coupons.csv"),
        "merchant_accounts": load_csv("merchant_accounts.csv"),
        "customers": load_csv("customers.csv"),
        "payment_instruments": load_csv("payment_instruments.csv"),
        "transactions": load_csv("transactions.csv"),
        "payment_attempts": load_csv("payment_attempts.csv"),
        "refunds": load_csv("refunds.csv"),
        "chargebacks": load_csv("chargebacks.csv"),
    }

    results = {
        "referential_integrity": check_referential_integrity(tables),
        "class_balance": check_class_balance(tables["customers"], tables["transactions"]),
        "ring_signal": check_ring_signal_strength(tables["customers"], tables["transactions"]),
    }

    print("\n" + "=" * 50)
    print("Validation summary")
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "⚠️  FAIL / WARNING"
        print(f"   {check_name}: {status}")

    if not all(results.values()):
        print("\n⚠️  Some checks failed or produced warnings - see details above.")
        print("Review before proceeding to Step 8 - don't ignore these.")
    else:
        print("\n✅ Dataset passed all validation checks.")


if __name__ == "__main__":
    main()