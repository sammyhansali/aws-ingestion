resource "aws_security_group" "rds" {
    name = "rds-terraform"
    description = "rds security group created via terraform"
    vpc_id = aws_vpc.main.id

}

resource "aws_vpc_security_group_ingress_rule" "my_ip_to_rds" {
    security_group_id = aws_security_group.rds.id
    description = "my ip TO rds"

    from_port = 5432
    to_port = 5432
    ip_protocol = "tcp"
    cidr_ipv4 = "73.119.47.26/32"
}

resource "aws_vpc_security_group_ingress_rule" "glue_to_rds" {
    security_group_id = aws_security_group.rds.id
    description = "glue TO rds"

    from_port = 5432
    to_port = 5432
    ip_protocol = "tcp"
    referenced_security_group_id = aws_security_group.glue.id
}

resource "aws_vpc_security_group_ingress_rule" "all_to_rds" {
    security_group_id = aws_security_group.rds.id
    description = "all ports TO rds. temporary just for testing"

    from_port = 5432
    to_port = 5432
    ip_protocol = "tcp"
    cidr_ipv4 = "0.0.0.0/0"
}

resource "aws_security_group" "glue" {
    name = "glue-terraform"
    description = "glue security group created via terraform"
    vpc_id = aws_vpc.main.id
}

resource "aws_vpc_security_group_egress_rule" "glue_outbound" {
    security_group_id = aws_security_group.glue.id
    ip_protocol = "-1"
    cidr_ipv4 = "0.0.0.0/0"
}