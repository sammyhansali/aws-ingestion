import argparse

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
        "host": "database-1.civiomsc0jqa.us-east-1.rds.amazonaws.com",
        "port": 5432,
        "dbname": "postgres",
        "user": "REDACTED_USER",
        "password": "REDACTED",
    },
}

COUNTS = {
    "customers": 5_000,
    "products": 500,
    "orders": 25_000,
    "order_items": 75_000,
}


def already_seeded(cur, table: str) -> bool:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0] > 0


def seed_customers(cur):
    sql = """
    insert into CUSTOMERS (customer_id, name, email, city, status)
    VALUES (%s, %s, %s, %s, %s)
    """
    to_insert = []

    for i in range(COUNTS["customers"]):
        customer_id = i + 1
        name = fake.unique.name()
        email = fake.unique.email()
        city = fake.city()
        status = fake.random_element(
            elements=["hyperactive", "active", "inactive", "churned"]
        )

        to_insert.append((customer_id, name, email, city, status))

    cur.executemany(sql, to_insert)


def seed_products(cur):
    sql = """
    INSERT INTO products (product_id, product_name, description, price, is_active)
    VALUES (%s, %s, %s, %s, %s)
    """
    to_insert = []

    for i in range(COUNTS["products"]):
        product_id = i + 1
        product_name = fake.unique.ecommerce_name()
        description = f"{fake.ecommerce_material()} {fake.ecommerce_category()} product. {fake.sentence()}"
        price = fake.ecommerce_price(as_int=False)
        is_active = fake.random_element(elements=[True, True, True, False])

        to_insert.append((product_id, product_name, description, price, is_active))

    cur.executemany(sql, to_insert)


def seed_orders(cur):
    sql = """
    INSERT INTO orders (order_id, customer_id, order_date, order_status, total_amount)
    VALUES (%s, %s, %s, %s, %s)
    """
    to_insert = []

    for i in range(COUNTS["orders"]):
        order_id = i + 1
        customer_id = fake.random_int(min=1, max=COUNTS["customers"])
        order_date = fake.date_time_between(start_date="-1y", end_date="now")
        order_status = fake.random_element(
            elements=["pending", "shipped", "delivered", "cancelled"]
        )
        total_amount = fake.ecommerce_price(as_int=False)

        to_insert.append(
            (order_id, customer_id, order_date, order_status, total_amount)
        )

    cur.executemany(sql, to_insert)


def seed_order_items(cur):
    sql = """
   INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price)
   VALUES (%s, %s, %s, %s, %s)
   """
    to_insert = []
    for i in range(COUNTS["order_items"]):
        order_item_id = i + 1
        order_id = fake.random_int(min=1, max=COUNTS["orders"])
        product_id = fake.random_int(min=1, max=COUNTS["products"])
        quantity = fake.random_int(min=1, max=5)
        unit_price = fake.ecommerce_price(as_int=False)

        to_insert.append((order_item_id, order_id, product_id, quantity, unit_price))

    cur.executemany(sql, to_insert)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["local", "rds"], default="local")
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIGS[args.env])
    cur = conn.cursor()

    for table, fn in [
        ("customers", seed_customers),
        ("products", seed_products),
        ("orders", seed_orders),
        ("order_items", seed_order_items),
    ]:
        if already_seeded(cur, table):
            print(f"Skipping {table}: already has data")
        else:
            print(f"Seeding {table}...")
            try:
                fn(cur)
                conn.commit()
                print(f"Done seeding {table}")
            except Exception as e:
                print(f"Error seeding {table}: {e}")
                conn.rollback()

    cur.close()
    conn.close()
