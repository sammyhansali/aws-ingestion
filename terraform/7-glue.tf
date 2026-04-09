resource "aws_glue_connection" "main" {
    name = "main"
    connection_properties = {
        JDBC_CONNECTION_URL = "jdbc:postgresql://${aws_db_instance.default.endpoint}/postgres"
        PASSWORD            = "REDACTED"
        USERNAME            = "REDACTED_USER"
    }
    physical_connection_requirements {
        availability_zone = "us-east-1a"
        security_group_id_list = [aws_security_group.glue.id]
        subnet_id = aws_subnet.one.id
    }
}

resource "aws_glue_job" "simulate_changes" {
    name = "1-batch-ingestion-full-vs-incremental_simulate-changes"
    description = "Simulate changes to the postgres database, for the full batch vs incremental batch aws ingestion project."
    role_arn = aws_iam_role.glue_role.arn
    max_capacity = "0.0625"
    max_retries = 0
    timeout = 2880
    connections = [aws_glue_connection.main.name]

    command {
        name = "pythonshell"
        script_location = "s3://${aws_s3_bucket.main.bucket}/1-batch-ingestion-full-vs-incremental/glue/scripts/simulate_changes.py"
        python_version = "3.9"
    }
}
resource "aws_glue_job" "full_load" {
    name = "1-batch-ingestion-full-vs-incremental_full-load"
    description = "Full load from the postgres database, for the full batch vs incremental batch aws ingestion project."
    role_arn = aws_iam_role.glue_role.arn
    max_capacity = "0.0625"
    max_retries = 0
    timeout = 2880
    connections = [aws_glue_connection.main.name]

    command {
        name = "pythonshell"
        script_location = "s3://${aws_s3_bucket.main.bucket}/1-batch-ingestion-full-vs-incremental/glue/scripts/full_load.py"
        python_version = "3.9"
    }

    default_arguments = {
        "--extra-py-files" = "s3://${aws_s3_bucket.main.bucket}/1-batch-ingestion-full-vs-incremental/glue/scripts/metrics.py",
        "--size" = "small"
        "library-set" = "analytics"
    }
}
resource "aws_glue_job" "incremental_load" {
    name = "1-batch-ingestion-full-vs-incremental_incremental-load"
    description = "Incremental load from the postgres database, for the full batch vs incremental batch aws ingestion project."
    role_arn = aws_iam_role.glue_role.arn
    max_capacity = "0.0625"
    max_retries = 0
    timeout = 2880
    connections = [aws_glue_connection.main.name]

    command {
        name = "pythonshell"
        script_location = "s3://${aws_s3_bucket.main.bucket}/1-batch-ingestion-full-vs-incremental/glue/scripts/incremental_load.py"
        python_version = "3.9"
    }

    default_arguments = {
        "--extra-py-files" = "s3://${aws_s3_bucket.main.bucket}/1-batch-ingestion-full-vs-incremental/glue/scripts/metrics.py",
        "--size" = "small"
        "library-set" = "analytics"
    }
}

resource "aws_glue_trigger" "hourly_simulate_changes" {
    name = "hourly_simulate_changes"
    type = "SCHEDULED"
    schedule = "cron(0 * * * ? *)"

    actions {
        job_name = aws_glue_job.simulate_changes.name
    }

}

resource "aws_glue_trigger" "on_simulate_ingest" {
    name = "on_simulate_ingest"
    type = "CONDITIONAL"

    predicate {
        conditions {
            job_name = aws_glue_job.simulate_changes.name
            state = "SUCCEEDED"
        }
    }

    actions {
        job_name = aws_glue_job.full_load.name
    }

    actions {
        job_name = aws_glue_job.incremental_load.name
    }

}