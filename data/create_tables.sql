create table customers (

    customer_id bigint primary key,
    name varchar(255) not null,
    email varchar(255) not null unique,
    city varchar(255),
    status varchar(255),
    created_at timestamp default current_timestamp,
    updated_at timestamp default current_timestamp
)
;

create table products (
    product_id bigint primary key,
    product_name varchar(255) not null,
    description text,
    price decimal(10, 2) not null,
    is_active boolean default true,
    created_at timestamp default current_timestamp,
    updated_at timestamp default current_timestamp
)
;

create table orders (
    order_id bigint primary key,
    customer_id bigint not null references customers(customer_id),
    order_date timestamp default current_timestamp,
    order_status varchar(255),
    total_amount decimal(10, 2) not null,
    created_at timestamp default current_timestamp,
    updated_at timestamp default current_timestamp

)
;

create table order_items (
    order_item_id bigint primary key,
    order_id bigint not null references orders(order_id),
    product_id bigint not null references products(product_id),
    quantity int not null,
    unit_price decimal(10, 2) not null,
    created_at timestamp default current_timestamp,
    updated_at timestamp default current_timestamp
)
;