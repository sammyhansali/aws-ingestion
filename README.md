# AWS Ingestion

A series of mini-projects to build and analyze tradeoffs of different data ingestion techniques in AWS.

***Tags:** SQL, Python, AWS, Terraform, Ingestion, Batch, Full, Incremental, CDC, Streaming*

---

# Main Takeaways
I like to frame my main takeaways in a question & answer format, so that it makes it easier to review and test my knowledge later. Below are the things that I have learned from each project.

### 1: Batch Ingestion (Full vs Incremental)
> What are the main (quantifiable) tradeoffs to consider when picking a batch ingestion strategy?

answer

> When would I use a full load?

answer

> When would I use an incremental loading strategy?

answer

> What causes incremental pipelines to break?

answer

> What is the purpose of Change Data Capture (CDC)?

answer

---

# Results

## 1: Batch Ingestion (Full vs Incremental)
**Goals:** Build two batch ingestion pipelines (full and incremental) to ingest data from an OLTP database to an S3 data lake every 5 minutes. Evaluate the cost, performance, and correctness of each pipeline. Understand the detailed tradeoffs between these two approaches for keeping a data lake in sync with a database.

- **Source:** RDS Postgres database.
    - Every 5 minutes: inserts, updates, soft deletes, and hard deletes.
    - Each table gets 100 changes in total.
        - Customers: 100 updates.
        - Products: 70 updates, 30 soft deletes.
        - Orders: 50 updates, 50 new records.
        - Order Items: 70 new records, 30 hard deletes.
- **Ingestion & Transformation:** Glue.
- **Target:** S3.
    &rarr; Landing Zone (raw, csv).
    &rarr; Processed Zone (partitioned, parquet).

![](./images/1-batch-ingestion-full-vs-incremental.drawio.png)

**Seeding:** The source tables were seeded with a python script that creates a connection to the RDS database, creates the tables if they do not exist already, truncates them, and then copies synthetically generated data into them. 

**Orchestration:** Two glue triggers were created. One to run the script for simulating changes on the RDS database every 5 minutes. And if that script succeeds, the other trigger runs both ingestion pipelines.

**Querying:** I used DuckDB as a sort of swiss-army-knife of querying. Quick sanity checks, ad-hoc exploration, and building out the analysis script.

**Data Lake Structure:**

```
1-batch-ingestion-full-vs-incremental/
├── glue
│   └── scripts
│       ├── full_load.py
│       ├── incremental_load.py
│       ├── metrics.py
│       └── simulate_changes.py
├── incremental_checkpoint.json
├── metrics
│   └── metrics.csv
├── processing
│   ├── full
│   │   ├── customers
│   │   │   └── data.parquet
│   │   ├── order_items
│   │   │   └── data.parquet
│   │   ├── orders
│   │   │   └── data.parquet
│   │   └── products
│   │       └── data.parquet
│   └── incremental
│       ├── customers/ (73 items)
│       ├── order_items/ (73 items)
│       ├── orders/ (73 items)
│       └── products/ (73 items)
└── raw
    ├── full
    │   ├── customers.csv
    │   ├── order_items.csv
    │   ├── orders.csv
    │   └── products.csv
    └── incremental
        ├── customers/ (73 items)
        ├── order_items/ (73 items)
        ├── orders/ (73 items)
        └── products/ (73 items)
```

### Analysis
In all, each pipeline was run 73 times. There are three main factors that I kept in mind while performing the analysis.

- **Cost:** What is the cost model and how do costs look like they would scale for each pipeline given bigger and bigger datasets?
- **Performance:** Runtime, memory usage, and scalability?
- **Correctness:** Does the data in S3 reflect the source?

#### Cost
To estimate the cost of each run, I calculated
`cost_usd = (runtime_seconds / 3600) * GLUE_DPU * GLUE_DPU_PRICE_PER_HOUR` (where `GLUE_DPU = 0.0625` (because I configured my Glue jobs to use only 1/16th of a DPU) and `GLUE_DPU_PRICE_PER_HOUR = 0.44`). 

<p align="center">  
    <img src="./analysis/output/cost.png" width=100%>
    Figure 1. Cumulative Cost Over Time: Full vs Incremental
</p>

Figure 1 shows the cumulative cost over time for each pipeline. As you can see, there is quite a big gap between the two. This gap is better understood upon inspection of Table 1, where it becomes clear that the full pipeline costs an order of magnitude more. If you were to run these pipelines hourly for a whole month, you should expect to spend about **\$0.074** and **$0.009** on full and incremental, respectively.

<div align="center">

| job_type    |   total_runs |   total_cost_usd |   avg_cost_per_run_usd |   projected_daily_usd |   projected_monthly_usd |
|:------------|-------------:|-----------------:|-----------------------:|----------------------:|------------------------:|
| full        |           73 |         0.007491 |               0.000103 |                0.0025 |                  0.0739 |
| incremental |           73 |         0.000881 |               1.2e-05  |                0.0003 |                  0.0087 |

Table 1. Cost Data: Full vs Incremental
</div>

#### Performance

#### Correctness

### Running the Code
**`...detailed code instructions go here...`**

--- 

# Methods

## Data
For the projects, I decided to create a single synthetic dataset with a simple data model, shown below. 

**... (add more explanation to how the data was generated and assumptions) ...**
<p align="center">  
    <img src="./images/data-model_1-batch-ingestion-full-vs-incremental.png" width=100%>
</p>

**... (preview of the data here) ...**

Because many of the projects involve some sort of benchmarking, the data is also split into three sizes (small, medium, large).

**... (explanation of the sizes here) ...**

## Infrastructure as Code (IaC)
One side goal of mine when embarking on these projects was to get some extra practice using Terraform to write my AWS infrastructure as code. I see this skillset as becoming pivotally important for data engineers to master (even in single-cloud environments!) as the DE discipline continues to converge more and more with DevOps (not to mention its pretty satisfying to be able to spin everything up so conveniently).

The way I practiced this was as simple as (1) building out the project normally, via AWS console + CLI, and then (2) replicating my exact environment/results with Terraform. For simulating a real production environment, I placed my terraform backend in the root bucket for this repo, `sh26-aws-ingestion-tf`.

## AI
There are two main use-cases for AI (I'm using "AI" here as a shorthand for things like large language models, agents, and so on) in the realm of software: learning and coding. I believe that it is better for my long-term development as an engineer, systems thinker, and problem solver to avoid (as much as possible) just using AI to generate all of the code. Not only have studies shown that [AI coding assistance can significantly decrease mastery at the benefit of slightly faster speed](https://www.anthropic.com/research/AI-assistance-coding-skills), but it also takes away a lot of the joy and craft of figuring things out for yourself.

That being said, I will still occasionally code generate on personal projects meant for learning. But usually only for boring / routine tasks I can do in my sleep. Or for things such as plotting with matplotlib, which I do not need to learn the intricacies of and am happy delegating to AI. My main use of AI is still learning things quicker, for which I find it indispensable. [AI was also helpful to come up with some of the project ideas](https://chatgpt.com/share/69c590de-e868-8328-b018-b9dafb5f5912) I executed in this repository, as well as ideas on questions to ask myself, experiments to perform, overall structure, and so on.

## Diagrams
The architecture diagrams were created with draw.io and the data model diagrams were created with dbdiagram.io.

--- 

# Conclusion
This was really fun and I learned a lot.

**... (summary of my main takeaways section here) ...**

I highly recommend that if you are interested in getting a deep understanding of data ingestion on AWS, enough that you can comfortably build out quick pipelines and have deep discussions about pipeline architecture and design tradeoffs, that you do something similar.