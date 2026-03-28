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

COUNTS = {
    "customers": 10_000,
    "products": 1_000,
    "orders": 50_000,
    "order_items": 150_000,
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
    pass


def seed_order_items(cur):
    pass


if __name__ == "__main__":
    conn = psycopg2.connect(**DB_CONFIG)
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
            fn(cur)
            conn.commit()
            print(f"Done seeding {table}")

    cur.close()
    conn.close()
