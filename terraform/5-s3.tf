import {
  to = aws_s3_bucket.main
  id = "sh26-aws-ingestion"
}

resource "aws_s3_bucket" "main" {
    bucket = "sh26-aws-ingestion"
}