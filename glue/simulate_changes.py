import argparse
import random
from datetime import datetime, timedelta

import psycopg2

CITIES = [
    "New York",
    "Los Angeles",
    "Chicago",
    "Houston",
    "Phoenix",
    "Philadelphia",
    "San Antonio",
    "San Diego",
    "Dallas",
    "San Jose",
]
STATUSES = ["hyperactive", "active", "inactive", "churned"]
ORDER_STATUSES = ["pending", "shipped", "delivered", "cancelled"]


def random_city() -> str:
    return random.choice(CITIES)


def random_status() -> str:
    return random.choice(STATUSES)


def random_order_status() -> str:
    return random.choice(ORDER_STATUSES)


def random_price() -> float:
    return round(random.uniform(1.0, 999.99), 2)


def random_date_within_last_year() -> datetime:
    days_ago = random.randint(0, 365)
    return datetime.now() - timedelta(days=days_ago)


DB_CONFIGS = {
    # "local": {
    #     "host": "localhost",
    #     "port": 5432,
    #     "user": "admin",
    #     "password": "admin",
    # },
    "rds": {
        "host": "database-1.civiomsc0jqa.us-east-1.rds.amazonaws.com",
        "port": 5432,
        "dbname": "postgres",
        "user": "REDACTED_USER",
        "password": "REDACTED",
    },
}

CHANGES_PER_RUN = 100


def get_ids(cur, table: str, id_col: str) -> list:
    cur.execute(f"SELECT {id_col} FROM {table}")
    return [row[0] for row in cur.fetchall()]


def simulate_customers(cur):
    """
    Simulate 100 changes to customers table by updating the city, status of 100 customers.
    """
    ids = get_ids(cur, "customers", "customer_id")
    ids = random.sample(ids, k=CHANGES_PER_RUN)

    sql = """
    UPDATE customers 
    SET city = %s, status = %s, updated_at = current_timestamp
    WHERE customer_id = %s
    """
    to_update = []
    for id in ids:
        to_update.append((random_city(), random_status(), id))

    cur.executemany(sql, to_update)


def simulate_products(cur, product_ids: list):
    # price updates: 70% of changes
    # soft deletes: 30% of changes
    price_update_ids = random.sample(product_ids, k=int(CHANGES_PER_RUN * 0.7))
    soft_delete_ids = random.sample(product_ids, k=int(CHANGES_PER_RUN * 0.3))

    cur.executemany(
        "UPDATE products SET price = %s, updated_at = current_timestamp WHERE product_id = %s",
        [(random_price(), id) for id in price_update_ids],
    )

    cur.executemany(
        "UPDATE products SET is_active = false, updated_at = current_timestamp WHERE product_id = %s",
        [(id,) for id in soft_delete_ids],
    )


def simulate_orders(cur, order_ids: list, mx_cust_id: int):
    # order status updates: 50% of changes
    # new orders: 50% of changes
    status_update_ids = random.sample(order_ids, k=int(CHANGES_PER_RUN * 0.5))
    cur.executemany(
        """
        UPDATE orders
        SET
            order_status = %s,
            updated_at = current_timestamp
        WHERE order_id = %s
        """,
        [(random_order_status(), id) for id in status_update_ids],
    )

    to_insert = []
    mx = max(order_ids)
    for i in range(int(CHANGES_PER_RUN * 0.5)):
        order_id = mx + i + 1
        customer_id = random.randint(1, mx_cust_id)
        order_date = random_date_within_last_year()
        order_status = random_order_status()
        total_amount = random_price()

        to_insert.append(
            (order_id, customer_id, order_date, order_status, total_amount)
        )

    cur.executemany(
        """
        INSERT INTO orders (order_id, customer_id, order_date, order_status, total_amount)
        VALUES (%s, %s, %s, %s, %s)""",
        to_insert,
    )


def simulate_order_items(cur, order_ids: list, product_ids: list, order_item_ids: list):
    # inserts: 70% of changes
    # deletes: 30% of changes
    mx = max(order_item_ids)
    to_insert = []
    for i in range(int(CHANGES_PER_RUN * 0.7)):
        order_item_id = mx + i + 1
        order_id = random.choice(order_ids)
        product_id = random.choice(product_ids)
        quantity = random.randint(1, 5)
        unit_price = random_price()
        to_insert.append((order_item_id, order_id, product_id, quantity, unit_price))

    cur.executemany(
        "INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s, %s)",
        to_insert,
    )

    delete_ids = random.sample(order_item_ids, k=int(CHANGES_PER_RUN * 0.3))
    cur.executemany(
        "DELETE FROM order_items WHERE order_item_id = %s",
        [(id,) for id in delete_ids],
    )


if __name__ == "__main__":
    _, _ = argparse.ArgumentParser().parse_known_args()

    conn = psycopg2.connect(**DB_CONFIGS["rds"])
    cur = conn.cursor()

    customer_ids = get_ids(cur, "customers", "customer_id")
    product_ids = get_ids(cur, "products", "product_id")
    order_ids = get_ids(cur, "orders", "order_id")
    order_item_ids = get_ids(cur, "order_items", "order_item_id")

    for label, fn, kwargs in [
        ("customers", simulate_customers, {}),
        ("products", simulate_products, {"product_ids": product_ids}),
        (
            "orders",
            simulate_orders,
            {"order_ids": order_ids, "mx_cust_id": max(customer_ids)},
        ),
        (
            "order_items",
            simulate_order_items,
            {
                "order_ids": order_ids,
                "product_ids": product_ids,
                "order_item_ids": order_item_ids,
            },
        ),
    ]:
        print(f"Simulating changes for {label}...")
        try:
            fn(cur, **kwargs)
            conn.commit()
            print(f"Done simulating {label}")
        except Exception as e:
            print(f"Error simulating {label}: {e}")
            conn.rollback()

    cur.close()
    conn.close()
