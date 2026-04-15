import os

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv

load_dotenv()

S3_BUCKET = "sh26-aws-ingestion-tf"
S3_PREFIX = "1-batch-ingestion-full-vs-incremental"
METRICS_PATH = f"s3://{S3_BUCKET}/{S3_PREFIX}/metrics/metrics.csv"
INCREMENTAL_PARQUET = f"s3://{S3_BUCKET}/{S3_PREFIX}/processing/incremental"
RDS_CONN = f"host={os.environ['RDS_DB_HOST']} port=5432 dbname=postgres user={os.environ['RDS_DB_USER']} password={os.environ['RDS_DB_PASSWORD']}"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PALETTE = {"full": "#4C9BE8", "incremental": "#E87D4C"}
TABLES = ["customers", "products", "orders", "order_items"]
PRIMARY_KEYS = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
}


def make_con():
    con = duckdb.connect()
    con.execute("install httpfs; load httpfs;")
    con.execute(
        f"""
        create or replace secret secret (
            type s3,
            provider config,
            key_id '{os.environ["AWS_ACCESS_KEY_ID"]}',
            secret '{os.environ["AWS_SECRET_ACCESS_KEY"]}',
            region 'us-east-1'
        )
        """
    )
    return con


# ── Load metrics ──────────────────────────────────────────────────────────────
print("Loading metrics...")
con = make_con()
df = con.execute(
    f"""
select
    *,
    row_number() over 
        (partition by job_type, "table" order by run_timestamp) as run_id
from read_csv('{METRICS_PATH}')
"""
).df()
con.close()
print(f"  {len(df)} rows loaded")

# ── Correctness ───────────────────────────────────────────────────────────────
print("\nCorrectness: querying source and incremental target row counts...")
con = make_con()
con.execute("install postgres; load postgres;")
con.execute(f"attach '{RDS_CONN}' as rds (type postgres);")

src_records, tgt_records = [], []
for table in TABLES:
    src = con.execute(f"select count(*) from rds.{table}").fetchone()[0]
    key = PRIMARY_KEYS[table]
    tgt = con.execute(f"""
        with deduped as (
            select {key},
                   row_number() over (partition by {key} order by updated_at desc) as rn
            from read_parquet('{INCREMENTAL_PARQUET}/{table}/run_ts=*/data.parquet')
        )
        select count(*) from deduped where rn = 1
    """).fetchone()[0]
    src_records.append(src)
    tgt_records.append(tgt)
    print(f"  {table}: src={src:,}  tgt={tgt:,}  drift={tgt - src:+,}")

con.close()

correctness = pd.DataFrame({"table": TABLES, "src": src_records, "tgt": tgt_records})
correctness["drift"] = correctness["tgt"] - correctness["src"]
correctness.to_markdown(os.path.join(OUTPUT_DIR, "correctness.md"), index=False)

# ── Performance ───────────────────────────────────────────────────────────────
print("\nPerformance:")
con = duckdb.connect()
perf = con.execute("""
    select
        job_type,
        "table",
        round(median(runtime_seconds), 3) as median_runtime_s,
        round(min(runtime_seconds), 3)    as min_runtime_s,
        round(max(runtime_seconds), 3)    as max_runtime_s,
        round(median(memory_peak_mb), 3)  as median_memory_mb
    from df
    group by job_type, "table"
    order by "table", job_type
""").df()
con.close()
print(perf.to_string(index=False))
perf.to_markdown(os.path.join(OUTPUT_DIR, "performance.md"), index=False)

# ── Cost ──────────────────────────────────────────────────────────────────────
print("\nCost:")
con = duckdb.connect()
cost = con.execute("""
    with per_run as (
        select
            job_type,
            run_id,
            sum(estimated_cost_usd) as run_cost_usd
        from df
        group by job_type, run_id
    )
    select
        job_type,
        count(*)                               as total_runs,
        round(sum(run_cost_usd), 6)            as total_cost_usd,
        round(avg(run_cost_usd), 6)            as avg_cost_per_run_usd,
        round(avg(run_cost_usd) * 24, 4)       as projected_daily_usd,
        round(avg(run_cost_usd) * 24 * 30, 4)  as projected_monthly_usd
    from per_run
    group by job_type
    order by job_type
""").df()
con.close()
print(cost.to_string(index=False))
cost.to_markdown(os.path.join(OUTPUT_DIR, "cost.md"), index=False)

con = duckdb.connect()
cost_per_run = con.execute("""
    with with_run_id as (
        select
            *
        from df
    ),
    per_run as (
        select
            job_type,
            run_id,
            sum(estimated_cost_usd) as run_cost_usd
        from with_run_id
        group by job_type, run_id
    )
    select
        job_type,
        run_id,
        run_cost_usd,
        sum(run_cost_usd) over (partition by job_type order by run_id) as cumulative_cost_usd
    from per_run
    order by job_type, run_id
""").df()
con.close()
cost_per_run.to_csv(os.path.join(OUTPUT_DIR, "cost_per_run.csv"), index=False)

# ── Plots ─────────────────────────────────────────────────────────────────────

# Runtime box plot
fig, axes = plt.subplots(1, 4, figsize=(16, 5))
for i, table in enumerate(TABLES):
    sns.boxplot(
        data=df[df["table"] == table],
        x="job_type",
        y="runtime_seconds",
        palette=PALETTE,
        ax=axes[i],
        order=["full", "incremental"],
    )
    axes[i].set_title(table, fontsize=12)
    axes[i].set_xlabel("")
    axes[i].set_ylabel("runtime (s)" if i == 0 else "")
fig.suptitle(
    "Runtime Distribution: Full vs Incremental", fontsize=14, fontweight="bold"
)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "runtime.png"), dpi=150)
plt.close()

# Cumulative cost
fig, ax = plt.subplots(figsize=(12, 5))
for job_type, color in PALETTE.items():
    subset = cost_per_run[cost_per_run["job_type"] == job_type]
    ax.plot(
        subset["run_id"],
        subset["cumulative_cost_usd"],
        label=job_type,
        color=color,
        linewidth=2,
    )
ax.set_xlabel("Run #")
ax.set_ylabel("Cumulative Cost (USD)")
ax.set_title("Cumulative Cost Over Time: Full vs Incremental", fontweight="bold")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "cost.png"), dpi=150)
plt.close()

# Correctness bar chart
x = np.arange(len(TABLES))
width = 0.35
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(x - width / 2, src_records, width, label="Source (RDS)", color=PALETTE["full"])
ax.bar(
    x + width / 2,
    tgt_records,
    width,
    label="Incremental Target (S3)",
    color=PALETTE["incremental"],
)
for i, (s, t) in enumerate(zip(src_records, tgt_records)):
    diff = t - s
    if diff != 0:
        ax.annotate(
            f"{'+' if diff > 0 else ''}{diff:,}",
            xy=(x[i] + width / 2, t),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            color="red",
            fontweight="bold",
            fontsize=10,
        )
ax.set_xticks(x)
ax.set_xticklabels(TABLES)
ax.set_ylabel("Row Count")
ax.set_title("Correctness: Source vs Incremental Target Row Counts", fontweight="bold")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "correctness.png"), dpi=150)
plt.close()
