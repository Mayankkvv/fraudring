"""
Functions that generate individual entity types for the FraudRing synthetic
dataset. Each function returns a list of dictionaries; generate_dataset.py
decides how to combine them and write CSVs. Kept separate from ring-assignment
logic (ring_designer.py) so each file has one clear job.
"""

import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()


def random_datetime_between(start: datetime, end: datetime) -> datetime:
    """Returns a random datetime between two datetimes."""
    delta_seconds = int((end - start).total_seconds())
    if delta_seconds <= 0:
        return start
    return start + timedelta(seconds=random.randint(0, delta_seconds))


def generate_addresses(count: int) -> list:
    addresses = []
    for i in range(count):
        addresses.append({
            "address_id": f"ADDR{i+1:05d}",
            "line1": fake.street_address(),
            "city": fake.city(),
            "state": fake.state(),
            "postal_code": fake.postcode(),
            "country": "India",
            "geo_lat": round(random.uniform(8.0, 34.0), 6),   # rough India latitude range
            "geo_lon": round(random.uniform(68.0, 97.0), 6),  # rough India longitude range
        })
    return addresses


def generate_devices(count: int) -> list:
    os_choices = ["Android", "iOS", "Windows", "macOS", "Linux"]
    browser_choices = ["Chrome", "Safari", "Firefox", "Edge", "App-WebView"]
    devices = []
    for i in range(count):
        devices.append({
            "device_id": f"DEV{i+1:05d}",
            "device_fingerprint": fake.sha1()[:16],
            "os": random.choice(os_choices),
            "browser": random.choice(browser_choices),
        })
    return devices


def generate_ip_addresses(count: int) -> list:
    ip_addresses = []
    for i in range(count):
        subnet = f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}"
        ip_addresses.append({
            "ip_id": f"IP{i+1:05d}",
            "ip_address": f"{subnet}.{random.randint(1, 254)}",
            "subnet": subnet,
            "country": "India",
        })
    return ip_addresses


def generate_payment_instruments(customer_ids: list) -> list:
    """Each customer gets 1-2 payment instruments."""
    instrument_types = ["card", "upi", "wallet"]
    banks = ["HDFC", "ICICI", "SBI", "Axis", "Kotak", "Yes Bank", "IDFC First"]
    instruments = []
    counter = 1
    for customer_id in customer_ids:
        num_instruments = random.choice([1, 1, 2])  # most customers have 1, some have 2
        for _ in range(num_instruments):
            instruments.append({
                "instrument_id": f"PI{counter:05d}",
                "customer_id": customer_id,
                "type": random.choice(instrument_types),
                "masked_number": f"**** {random.randint(1000, 9999)}",
                "issuer_bank": random.choice(banks),
                "added_date": fake.date_between(start_date="-2y", end_date="today").isoformat(),
            })
            counter += 1
    return instruments


def generate_coupons(count: int) -> list:
    discount_types = ["percentage", "flat"]
    coupons = []
    for i in range(count):
        discount_type = random.choice(discount_types)
        value = round(random.uniform(5, 30), 2) if discount_type == "percentage" else round(random.uniform(50, 500), 2)
        coupons.append({
            "coupon_id": f"COUP{i+1:05d}",
            "code": fake.lexify(text="SAVE????").upper(),
            "discount_type": discount_type,
            "discount_value": value,
            "max_uses": random.choice([50, 100, 200, 500]),
            "campaign_id": f"CAMP{random.randint(1, 10):03d}",
        })
    return coupons


def generate_merchants(count: int) -> list:
    categories = ["electronics", "fashion", "groceries", "travel", "food_delivery", "digital_services", "gaming"]
    risk_tiers = ["low", "medium", "high"]
    merchants = []
    for i in range(count):
        merchants.append({
            "merchant_id": f"MERCH{i+1:04d}",
            "name": fake.company(),
            "category": random.choice(categories),
            "risk_tier": random.choices(risk_tiers, weights=[0.7, 0.2, 0.1])[0],
        })
    return merchants


def generate_customer_record(index: int, address_id: str, signup_date: datetime, ring_id) -> dict:
    return {
        "customer_id": f"CUST{index:05d}",
        "name": fake.name(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "signup_date": signup_date.isoformat(),
        "kyc_verified": random.random() > 0.1,   # 90% verified
        "address_id": address_id,
        "ring_id": ring_id,   # HIDDEN ground truth - never used as a model input feature
    }