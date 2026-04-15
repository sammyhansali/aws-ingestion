terraform {
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.92"
        }
    }
    backend "s3" {
        bucket = "sh26-aws-ingestion-tf"
        key = "terraform/state/1-batch-ingestion-full-vs-incremental.tfstate"
        region = "us-east-1"
        profile = "terraform-admin"
    }
}

provider "aws" {
    region = "us-east-1"
    profile = "terraform-admin"
}