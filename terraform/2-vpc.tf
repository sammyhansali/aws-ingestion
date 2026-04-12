resource "aws_vpc" "main" {
    cidr_block = "10.0.0.0/16"
    enable_dns_support = true
    enable_dns_hostnames = true
}

resource "aws_subnet" "one" {
    vpc_id = aws_vpc.main.id
    cidr_block = "10.0.1.0/24"
    availability_zone = "us-east-1a"
    map_public_ip_on_launch = true
}

resource "aws_subnet" "two" {
    vpc_id = aws_vpc.main.id
    cidr_block = "10.0.2.0/24"
    availability_zone = "us-east-1b"
    map_public_ip_on_launch = true
}

resource "aws_internet_gateway" "gw" {
    vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "main" {
    vpc_id = aws_vpc.main.id

    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = aws_internet_gateway.gw.id
    }
}

resource "aws_route_table_association" "one" {
    subnet_id = aws_subnet.one.id
    route_table_id = aws_route_table.main.id
}

resource "aws_route_table_association" "two" {
    subnet_id = aws_subnet.two.id
    route_table_id = aws_route_table.main.id
}

resource "aws_vpc_endpoint" "s3" {
    vpc_id = aws_vpc.main.id
    service_name = "com.amazonaws.us-east-1.s3"
    vpc_endpoint_type = "Gateway"
    route_table_ids = [aws_route_table.main.id]
}

resource "aws_vpc_endpoint" "secretsmanager" {
    vpc_id = aws_vpc.main.id
    service_name = "com.amazonaws.us-east-1.secretsmanager"
    vpc_endpoint_type   = "Interface"
    subnet_ids          = [aws_subnet.one.id]
    security_group_ids  = [aws_security_group.glue.id]
    private_dns_enabled = true
}