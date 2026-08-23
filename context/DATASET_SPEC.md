# FraudRing — Synthetic Dataset Specification

## Purpose
A synthetic, Razorpay-like payment dataset with **known ground truth**, so we can measure precision/recall/F1 honestly instead of guessing whether detection works.

## Entities

### customers
| field | type | notes |
|---|---|---|
| customer_id | string | primary key |
| name | string | synthetic |
| email | string | synthetic |
| phone | string | synthetic |
| signup_date | datetime | |
| kyc_verified | boolean | |
| account_age_days | int | derived from signup_date |
| address_id | FK -> addresses | |
| ring_id | string or null | **hidden ground-truth field** — never exposed as a model feature, evaluation-only |

### devices
| field | type | notes |
|---|---|---|
| device_id | string | primary key |
| device_fingerprint | string | simulates browser/app fingerprint |
| os | string | |
| browser | string | |
| first_seen | datetime | |
| last_seen | datetime | |

### ip_addresses
| field | type | notes |
|---|---|---|
| ip_id | string | primary key |
| ip_address | string | synthetic IPv4 |
| subnet | string | used for IP clustering |
| country | string | |

### addresses
| field | type | notes |
|---|---|---|
| address_id | string | primary key |
| line1, city, state, postal_code, country | string | |
| geo_lat, geo_lon | float | |

### payment_instruments
| field | type | notes |
|---|---|---|
| instrument_id | string | primary key |
| type | enum | card / upi / wallet |
| masked_number | string | e.g. `**** 4242` |
| issuer_bank | string | |
| added_date | datetime | |

### coupons
| field | type | notes |
|---|---|---|
| coupon_id | string | primary key |
| code | string | |
| discount_type | enum | percentage / flat |
| discount_value | float | |
| max_uses | int | used to detect abuse when exceeded |
| campaign_id | string | |

### merchant_accounts
| field | type | notes |
|---|---|---|
| merchant_id | string | primary key |
| name | string | |
| category | string | |
| risk_tier | enum | low / medium / high |

### transactions
| field | type | notes |
|---|---|---|
| transaction_id | string | primary key |
| customer_id | FK -> customers | |
| merchant_id | FK -> merchant_accounts | |
| device_id | FK -> devices | |
| ip_id | FK -> ip_addresses | |
| payment_instrument_id | FK -> payment_instruments | |
| coupon_id | FK -> coupons, nullable | |
| timestamp | datetime | |
| amount | float | |
| currency | string | default INR |
| status | enum | success / failed / pending |
| is_ring_transaction | boolean | **hidden ground-truth label**, derived from customer.ring_id |

### payment_attempts
| field | type | notes |
|---|---|---|
| attempt_id | string | primary key |
| transaction_id | FK -> transactions | |
| attempt_number | int | |
| result | enum | success / declined / error |
| timestamp | datetime | |

### refunds
| field | type | notes |
|---|---|---|
| refund_id | string | primary key |
| transaction_id | FK -> transactions | |
| amount | float | |
| reason | string | |
| requested_at | datetime | |
| approved | boolean | |

### chargebacks
| field | type | notes |
|---|---|---|
| chargeback_id | string | primary key |
| transaction_id | FK -> transactions | |
| reason | string | |
| filed_at | datetime | |
| resolved | boolean | |
| resolution | enum | merchant_won / customer_won / pending |

## Relationships (graph edges)
```text
customer --used_device--> device
customer --connected_from--> ip_address
customer --resides_at--> address
customer --owns--> payment_instrument
customer --used_coupon--> coupon
customer --made--> transaction
transaction --has--> refund
transaction --has--> chargeback
transaction --at--> merchant_account
```

## Ground truth: abuse ring design
Each customer has a hidden `ring_id` (`null` for ordinary customers). Customers sharing the same `ring_id` are generated with **deliberately overlapping signals**, so the graph layer can rediscover them without ever seeing `ring_id` directly:

| Pattern | How it's simulated |
|---|---|
| Account farming | Many customer accounts created in a short window, similar signup metadata |
| Device sharing | Ring members reuse a small pool of device_ids |
| IP clustering | Ring members transact from a small pool of subnets |
| Coupon abuse | Ring reuses the same coupon_id beyond its max_uses via different accounts |
| Refund abuse | Ring has an abnormally high refund/chargeback rate |
| Coordinated timing | Ring transactions cluster in tight time windows |
| High-velocity abuse | Rapid repeated transactions per account in short bursts |
| Low-and-slow abuse | Same ring, but spread over weeks specifically to evade velocity rules |

`ring_id` and `is_ring_transaction` are used **only** to compute precision/recall/F1 after detection runs — they are never fed into the ML model, graph engine, or LLM as input features. That would be cheating.

## Train / validation / test split
- Split **by timestamp**, not randomly: earliest 70% of transactions = train, next 15% = validation, final 15% = test.
- At least a few entire abuse rings must appear **only** in the test set, never in train — this tests whether detection generalizes to unseen rings rather than memorizing known ones.
- Both splits must contain a realistic mix of normal and ring-linked customers (rings should not be all-or-nothing in one split).

## Scale target
~50,000+ transactions, several thousand customers, a defined number of injected rings (exact counts finalized when we build the generator in the next step).