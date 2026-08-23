"""
Decides which customers secretly belong to a fraud ring, and which small
pool of devices/IPs each ring reuses. This is what makes rings discoverable
by the graph engine later - real fraud rings share infrastructure, they
don't invent a new device and IP for every single account.
"""

import random


def assign_rings(customer_ids: list, num_rings: int, ring_size_min: int, ring_size_max: int) -> dict:
    """
    Randomly assigns a subset of customers into rings.
    Returns: { customer_id: ring_id_or_None }
    """
    ring_assignment = {cid: None for cid in customer_ids}
    available_customers = customer_ids.copy()
    random.shuffle(available_customers)

    for ring_num in range(1, num_rings + 1):
        ring_id = f"RING{ring_num:03d}"
        ring_size = random.randint(ring_size_min, ring_size_max)

        if len(available_customers) < ring_size:
            print(f"⚠️  Not enough customers left for {ring_id} at full size; using remaining {len(available_customers)}")
            ring_size = len(available_customers)

        if ring_size == 0:
            print(f"⚠️  No customers left to assign to {ring_id}, skipping")
            continue

        ring_members = [available_customers.pop() for _ in range(ring_size)]
        for cid in ring_members:
            ring_assignment[cid] = ring_id

    return ring_assignment


def pick_shared_pool(pool: list, size: int) -> list:
    """Picks a small shared subset of infrastructure (devices/IPs) for a ring to reuse."""
    if size > len(pool):
        size = len(pool)
    return random.sample(pool, size)


def build_ring_infrastructure(ring_ids: list, device_ids: list, ip_ids: list,
                               shared_devices: int, shared_ips: int) -> dict:
    """
    For each ring, picks the shared devices/IPs its members will reuse.
    Returns: { ring_id: {"devices": [...], "ips": [...]} }
    """
    infrastructure = {}
    for ring_id in ring_ids:
        infrastructure[ring_id] = {
            "devices": pick_shared_pool(device_ids, shared_devices),
            "ips": pick_shared_pool(ip_ids, shared_ips),
        }
    return infrastructure