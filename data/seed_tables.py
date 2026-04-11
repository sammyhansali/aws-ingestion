import argparse
import csv
import io

import psycopg2
from faker import Faker
from faker_commerce import Provider as CommerceProvider

fake = Faker()
fake.add_provider(CommerceProvider)

DB_CONFIGS = {
    "local": {
        "host": "localhost",
        "port": 5432,
        "user": "admin",
        "password": "admin",
    },
    "rds": {
        # "host": "database-1.civiomsc0jqa.us-east-1.rds.amazonaws.com",
        "host": "REDACTED_RDS_HOST",
        "port": 5432,
        "dbname": "postgres",
        "user": "REDACTED_USER",
        "password": "REDACTED",
    },
}

COUNTS = {
    "customers": [1_000, 5_000, 10_000],
    "products": [100, 500, 1_000],
    "orders": [5_000, 25_000, 50_000],
    "order_items": [15_000, 75_000, 150_000],
}
IDXS = {
    "small": 0,
    "medium": 1,
    "large": 2,
}


def already_seeded(cur, table: str) -> bool:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0] > 0


def seed_customers(cur, idx):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for i in range(COUNTS["customers"][idx]):
        writer.writerow([
            i + 1,
            fake.unique.name(),
            fake.unique.email(),
            fake.city(),
            fake.random_element(elements=["hyperactive", "active", "inactive", "churned"]),
        ])
    buf.seek(0)
    cur.copy_expert("COPY customers (customer_id, name, email, city, status) FROM STDIN WITH CSV", buf)


def seed_products(cur, idx):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for i in range(COUNTS["products"][idx]):
        writer.writerow([
            i + 1,
            fake.unique.ecommerce_name(),
            f"{fake.ecommerce_material()} {fake.ecommerce_category()} product. {fake.sentence()}",
            fake.ecommerce_price(as_int=False),
            fake.random_element(elements=[True, True, True, False]),
        ])
    buf.seek(0)
    cur.copy_expert("COPY products (product_id, product_name, description, price, is_active) FROM STDIN WITH CSV", buf)


def seed_orders(cur, idx):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for i in range(COUNTS["orders"][idx]):
        writer.writerow([
            i + 1,
            fake.random_int(min=1, max=COUNTS["customers"][idx]),
            fake.date_time_between(start_date="-1y", end_date="now"),
            fake.random_element(elements=["pending", "shipped", "delivered", "cancelled"]),
            fake.ecommerce_price(as_int=False),
        ])
    buf.seek(0)
    cur.copy_expert("COPY orders (order_id, customer_id, order_date, order_status, total_amount) FROM STDIN WITH CSV", buf)


def seed_order_items(cur, idx):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for i in range(COUNTS["order_items"][idx]):
        writer.writerow([
            i + 1,
            fake.random_int(min=1, max=COUNTS["orders"][idx]),
            fake.random_int(min=1, max=COUNTS["products"][idx]),
            fake.random_int(min=1, max=5),
            fake.ecommerce_price(as_int=False),
        ])
    buf.seek(0)
    cur.copy_expert("COPY order_items (order_item_id, order_id, product_id, quantity, unit_price) FROM STDIN WITH CSV", buf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["local", "rds"], default="local")
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    args = parser.parse_args()

    idx = IDXS[args.size]

    conn = psycopg2.connect(**DB_CONFIGS[args.env])
    cur = conn.cursor()

    for table, fn in [
        ("customers", seed_customers),
        ("products", seed_products),
        ("orders", seed_orders),
        ("order_items", seed_order_items),
    ]:
        if already_seeded(cur, table):
            print(f"Truncating {table}: already has data")
            cur.execute(f"TRUNCATE TABLE {table} CASCADE;")

        print(f"Seeding {table}...")
        try:
            fn(cur, idx)
            conn.commit()
            print(f"Done seeding {table}")
        except Exception as e:
            print(f"Error seeding {table}: {e}")
            conn.rollback()

    cur.close()
    conn.close()
