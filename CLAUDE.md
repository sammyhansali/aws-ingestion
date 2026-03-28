# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A series of mini-projects comparing data ingestion techniques in AWS. Project 1 builds two AWS Glue batch ingestion pipelines (full load vs incremental) that ingest data from a local PostgreSQL OLTP database into partitioned Parquet files in S3 — then measures cost, speed, and correctness across three dataset sizes (small, medium, large).

Tech stack: Python 3.12, PostgreSQL (Docker), AWS Glue, S3 (Parquet), Terraform.

## Commands

**Start the local database:**
```bash
docker-compose up -d
```

**Run the project:**
```bash
python main.py
```

**Seed the database:**
```bash
python data/seed_tables.py
```

**Simulate data changes (for incremental testing):**
```bash
python data/simulate_changes.py
```

## Architecture

### Data Model (PostgreSQL source)
Four normalized OLTP tables — `customers`, `products`, `orders`, `order_items` — each with `created_at` / `updated_at` audit columns. The `updated_at` column is the key timestamp used to drive incremental loads.

### Ingestion Strategy
Two pipelines are compared:
- **Full load**: Reads entire source tables each run, overwrites S3 target
- **Incremental load**: Reads only rows changed since last run (using `updated_at`), merges into S3 target

### Infrastructure
- Source: Local PostgreSQL via Docker Compose (`localhost:5432`, credentials `admin`/`admin`)
- Ingestion: AWS Glue jobs (Python shell or Spark)
- Target: S3 bucket with Parquet files, partitioned by date or entity
- IaC: Terraform (planned) to replicate all AWS resources

### Key Files
- `data/create_tables.sql` — source schema DDL
- `data/seed_tables.py` — generates synthetic test data at small/medium/large scale
- `data/simulate_changes.py` — simulates INSERTs, UPDATEs, DELETEs for incremental testing
- `images/` — architecture and data model diagrams (draw.io / dbdiagram.io)
