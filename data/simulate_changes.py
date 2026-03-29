import random

import psycopg2
from faker import Faker
from faker_commerce import Provider as CommerceProvider

fake = Faker()
fake.add_provider(CommerceProvider)

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "admin",
    "password": "admin",
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
    city = fake.city()
    status = fake.random_element(
        elements=["hyperactive", "active", "inactive", "churned"]
    )
    to_update = []
    for id in ids:
        to_update.append((city, status, id))

    cur.executemany(sql, to_update)


def simulate_products(cur, product_ids: list):
    # price updates: 70% of changes
    # soft deletes: 30% of changes
    price_update_ids = random.sample(product_ids, k=int(CHANGES_PER_RUN * 0.7))
    soft_delete_ids = random.sample(product_ids, k=int(CHANGES_PER_RUN * 0.3))

    cur.executemany(
        "UPDATE products SET price = %s, updated_at = current_timestamp WHERE product_id = %s",
        [(fake.ecommerce_price(as_int=False), id) for id in price_update_ids],
    )

    cur.executemany(
        "UPDATE products SET is_active = false, updated_at = current_timestamp WHERE product_id = %s",
        [(id,) for id in soft_delete_ids],
    )


def simulate_orders(cur, order_ids: list, mx_cust_id: int):
    # order status updates: 50% of changes
    # new orders: 50% of changes
    status_update_ids = random.sample(order_ids, k=int(CHANGES_PER_RUN * 0.5))
    new_status = fake.random_element(
        elements=["pending", "shipped", "delivered", "cancelled"]
    )
    cur.executemany(
        """
        UPDATE orders
        SET
            order_status = %s,
            updated_at = current_timestamp
        WHERE order_id = %s
        """,
        [(new_status, id) for id in status_update_ids],
    )

    to_insert = []
    mx = max(order_ids)
    for i in range(int(CHANGES_PER_RUN * 0.5)):
        order_id = mx + i + 1
        customer_id = fake.random_int(min=1, max=mx_cust_id)
        order_date = fake.date_time_between(start_date="-1y", end_date="now")
        order_status = fake.random_element(
            elements=["pending", "shipped", "delivered", "cancelled"]
        )
        total_amount = fake.ecommerce_price(as_int=False)

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
        quantity = fake.random_int(min=1, max=5)
        unit_price = fake.ecommerce_price(as_int=False)
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
    conn = psycopg2.connect(**DB_CONFIG)
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
            {"order_ids": order_ids, "product_ids": product_ids, "order_item_ids": order_item_ids},
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
