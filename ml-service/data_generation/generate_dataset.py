"""
Main entry point for generating the FraudRing synthetic dataset.

Run with (from inside ml-service/, with venv activated):
    python -m data_generation.generate_dataset

Produces CSV files in data/raw/ for every entity in context/DATASET_SPEC.md,
including hidden ground-truth fields (ring_id, is_ring_transaction) that are
used only for evaluation later - never as model input features.
"""

import os
import random
import sys
from datetime import datetime

import pandas as pd

from data_generation import config
from data_generation.entity_generators import (
    random_datetime_between,
    generate_addresses,
    generate_devices,
    generate_ip_addresses,
    generate_payment_instruments,
    generate_coupons,
    generate_merchants,
    generate_customer_record,
)
from data_generation.ring_designer import assign_rings, build_ring_infrastructure


def generate_customers(num_customers, addresses, ring_assignment, start_date, end_date) -> list:
    customers = []
    for i in range(1, num_customers + 1):
        customer_id = f"CUST{i:05d}"
        address = random.choice(addresses)
        signup_date = random_datetime_between(start_date, end_date)
        ring_id = ring_assignment.get(customer_id)
        customers.append(generate_customer_record(i, address["address_id"], signup_date, ring_id))
    return customers


def generate_transactions(customers, merchants, devices, ip_addresses, instruments, coupons,
                           ring_infrastructure, start_date, end_date) -> list:
    """
    Ring members transact more often and disproportionately reuse their
    ring's shared devices/IPs and coupons - these are the signals the
    graph engine will pick up on later without ever seeing ring_id.
    """
    transactions = []
    txn_counter = 1

    instruments_by_customer = {}
    for instrument in instruments:
        instruments_by_customer.setdefault(instrument["customer_id"], []).append(instrument["instrument_id"])

    device_ids = [d["device_id"] for d in devices]
    ip_ids = [ip["ip_id"] for ip in ip_addresses]
    coupon_ids = [c["coupon_id"] for c in coupons]
    merchant_ids = [m["merchant_id"] for m in merchants]

    for customer in customers:
        customer_id = customer["customer_id"]
        ring_id = customer["ring_id"]
        customer_instruments = instruments_by_customer.get(customer_id)

        if not customer_instruments:
            continue  # shouldn't happen, but guards against mismatched counts

        base_count = config.AVG_TRANSACTIONS_PER_CUSTOMER
        num_transactions = (
            int(base_count * config.RING_TRANSACTION_MULTIPLIER)
            if ring_id else
            random.randint(max(1, base_count - 5), base_count + 5)
        )

        for _ in range(num_transactions):
            timestamp = random_datetime_between(start_date, end_date)

            if ring_id and ring_id in ring_infrastructure:
                device_id = random.choice(ring_infrastructure[ring_id]["devices"])
                ip_id = random.choice(ring_infrastructure[ring_id]["ips"])
            else:
                device_id = random.choice(device_ids)
                ip_id = random.choice(ip_ids)

            use_coupon = random.random() < (0.4 if ring_id else 0.1)
            coupon_id = random.choice(coupon_ids) if use_coupon and coupon_ids else None
            status = random.choices(["success", "failed", "pending"], weights=[0.85, 0.1, 0.05])[0]

            transactions.append({
                "transaction_id": f"TXN{txn_counter:06d}",
                "customer_id": customer_id,
                "merchant_id": random.choice(merchant_ids),
                "device_id": device_id,
                "ip_id": ip_id,
                "payment_instrument_id": random.choice(customer_instruments),
                "coupon_id": coupon_id,
                "timestamp": timestamp.isoformat(),
                "amount": round(random.uniform(100, 15000), 2),
                "currency": "INR",
                "status": status,
                "is_ring_transaction": ring_id is not None,
            })
            txn_counter += 1

    return transactions


def generate_payment_attempts(transactions) -> list:
    attempts = []
    counter = 1
    for txn in transactions:
        num_attempts = 1 if txn["status"] == "success" else random.randint(1, 3)
        for attempt_num in range(1, num_attempts + 1):
            is_final = attempt_num == num_attempts
            result = txn["status"] if is_final else random.choice(["declined", "error"])
            attempts.append({
                "attempt_id": f"PA{counter:06d}",
                "transaction_id": txn["transaction_id"],
                "attempt_number": attempt_num,
                "result": result,
                "timestamp": txn["timestamp"],
            })
            counter += 1
    return attempts


def generate_refunds(transactions) -> list:
    refunds = []
    counter = 1
    reasons = ["product_not_received", "not_as_described", "duplicate_charge", "customer_changed_mind"]
    for txn in transactions:
        if txn["status"] != "success":
            continue
        refund_chance = 0.35 if txn["is_ring_transaction"] else 0.05  # refund abuse pattern
        if random.random() < refund_chance:
            refunds.append({
                "refund_id": f"REF{counter:05d}",
                "transaction_id": txn["transaction_id"],
                "amount": txn["amount"],
                "reason": random.choice(reasons),
                "requested_at": txn["timestamp"],
                "approved": random.random() > 0.3,
            })
            counter += 1
    return refunds


def generate_chargebacks(transactions) -> list:
    chargebacks = []
    counter = 1
    reasons = ["unauthorized_transaction", "goods_not_received", "billing_error"]
    for txn in transactions:
        if txn["status"] != "success":
            continue
        chargeback_chance = 0.08 if txn["is_ring_transaction"] else 0.005
        if random.random() < chargeback_chance:
            chargebacks.append({
                "chargeback_id": f"CB{counter:05d}",
                "transaction_id": txn["transaction_id"],
                "reason": random.choice(reasons),
                "filed_at": txn["timestamp"],
                "resolved": random.random() > 0.4,
                "resolution": random.choice(["merchant_won", "customer_won", "pending"]),
            })
            counter += 1
    return chargebacks


def save_csv(records: list, filename: str, output_dir: str) -> None:
    """Writes a list of dicts to CSV, creating the output directory if needed."""
    if not records:
        print(f"⚠️  No records generated for {filename}, skipping file write")
        return
    try:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        pd.DataFrame(records).to_csv(filepath, index=False)
        print(f"✅ Wrote {len(records):>7,} rows -> {filepath}")
    except OSError as error:
        print(f"❌ Failed to write {filename}: {error}")
        sys.exit(1)


def main():
    print("FraudRing synthetic dataset generator")
    print("=" * 50)

    random.seed(config.RANDOM_SEED)

    try:
        start_date = datetime.fromisoformat(config.START_DATE)
        end_date = datetime.fromisoformat(config.END_DATE)
    except ValueError as error:
        print(f"❌ Invalid START_DATE/END_DATE in config.py: {error}")
        sys.exit(1)

    if end_date <= start_date:
        print("❌ END_DATE must be after START_DATE in config.py")
        sys.exit(1)

    print("Generating reference entities...")
    addresses = generate_addresses(config.NUM_CUSTOMERS)
    devices = generate_devices(config.NUM_DEVICES)
    ip_addresses = generate_ip_addresses(config.NUM_IP_ADDRESSES)
    coupons = generate_coupons(config.NUM_COUPONS)
    merchants = generate_merchants(config.NUM_MERCHANTS)

    print("Assigning customers to abuse rings...")
    customer_ids = [f"CUST{i:05d}" for i in range(1, config.NUM_CUSTOMERS + 1)]
    ring_assignment = assign_rings(
        customer_ids, config.NUM_RINGS, config.RING_SIZE_MIN, config.RING_SIZE_MAX
    )
    ring_ids = sorted(set(rid for rid in ring_assignment.values() if rid is not None))
    ring_infrastructure = build_ring_infrastructure(
        ring_ids,
        device_ids=[d["device_id"] for d in devices],
        ip_ids=[ip["ip_id"] for ip in ip_addresses],
        shared_devices=config.RING_SHARED_DEVICES,
        shared_ips=config.RING_SHARED_IPS,
    )

    print("Generating customers...")
    customers = generate_customers(config.NUM_CUSTOMERS, addresses, ring_assignment, start_date, end_date)

    print("Generating payment instruments...")
    instruments = generate_payment_instruments([c["customer_id"] for c in customers])

    print("Generating transactions (this can take a moment)...")
    transactions = generate_transactions(
        customers, merchants, devices, ip_addresses, instruments, coupons,
        ring_infrastructure, start_date, end_date,
    )

    print("Generating payment attempts, refunds, and chargebacks...")
    payment_attempts = generate_payment_attempts(transactions)
    refunds = generate_refunds(transactions)
    chargebacks = generate_chargebacks(transactions)

    print("\nWriting CSV files...")
    save_csv(addresses, "addresses.csv", config.OUTPUT_DIR)
    save_csv(devices, "devices.csv", config.OUTPUT_DIR)
    save_csv(ip_addresses, "ip_addresses.csv", config.OUTPUT_DIR)
    save_csv(coupons, "coupons.csv", config.OUTPUT_DIR)
    save_csv(merchants, "merchant_accounts.csv", config.OUTPUT_DIR)
    save_csv(customers, "customers.csv", config.OUTPUT_DIR)
    save_csv(instruments, "payment_instruments.csv", config.OUTPUT_DIR)
    save_csv(transactions, "transactions.csv", config.OUTPUT_DIR)
    save_csv(payment_attempts, "payment_attempts.csv", config.OUTPUT_DIR)
    save_csv(refunds, "refunds.csv", config.OUTPUT_DIR)
    save_csv(chargebacks, "chargebacks.csv", config.OUTPUT_DIR)

    num_ring_customers = sum(1 for c in customers if c["ring_id"] is not None)
    print("\n" + "=" * 50)
    print("Summary")
    print(f"  Customers:    {len(customers):,} ({num_ring_customers:,} in {len(ring_ids)} rings)")
    print(f"  Transactions: {len(transactions):,}")
    print(f"  Refunds:      {len(refunds):,}")
    print(f"  Chargebacks:  {len(chargebacks):,}")
    print("Done. Files are in:", config.OUTPUT_DIR)


if __name__ == "__main__":
    main()