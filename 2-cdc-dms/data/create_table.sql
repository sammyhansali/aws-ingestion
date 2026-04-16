create table if not exists transactions (
    id serial primary key,
    user_id integer not null,
    amount numeric(10,2) not null,
    status varchar(20) not null default 'pending',
    metadata jsonb,
    version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
)
;


create or replace function fn_version_increment()
returns trigger as $$
begin
    new.version := old.version + 1;
    new.updated_at := now();
    return new;
end;
$$ language plpgsql;


create or replace trigger tr_version_increment
before update on transactions
for each row
execute function fn_version_increment()
;


alter table transactions
    replica identity full;