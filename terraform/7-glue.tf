resource "aws_glue_connection" "main" {
    name = "main"
    connection_properties = {
        JDBC_CONNECTION_URL = "jdbc:postgresql://database-1.civiomsc0jqa.us-east-1.rds.amazonaws.com:5432/postgres"
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
# resource "aws_glue_job" "full_load" {}
# resource "aws_glue_job" "incremental_load" {}