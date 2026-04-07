resource "aws_db_subnet_group" "default" {
    name = "main"
    subnet_ids = [aws_subnet.one.id, aws_subnet.two.id]
}

resource "aws_db_instance" "default" {
    allocated_storage    = 20
    db_name              = "mydb"
    engine               = "postgres"
    engine_version       = "17"
    instance_class       = "db.t3.micro"
    username             = "dempuser"
    password             = "password"
    vpc_security_group_ids = [aws_security_group.rds.id]
    db_subnet_group_name = aws_db_subnet_group.default.name
    publicly_accessible = true
    skip_final_snapshot  = true
}