terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Get default VPC and subnets
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security Groups
resource "aws_security_group" "rds" {
  name_prefix = "diavgeia-rds-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Consider restricting to your IP
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "diavgeia-rds-sg"
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "diavgeia-redis-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Consider restricting to your IP
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "diavgeia-redis-sg"
  }
}

resource "aws_security_group" "opensearch" {
  name_prefix = "diavgeia-opensearch-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Consider restricting to your IP
  }

  ingress {
    from_port   = 9200
    to_port     = 9200
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Consider restricting to your IP
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "diavgeia-opensearch-sg"
  }
}

resource "aws_security_group" "mq" {
  name_prefix = "diavgeia-mq-"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 5671
    to_port     = 5672
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Consider restricting to your IP
  }

  ingress {
    from_port   = 15672
    to_port     = 15672
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Consider restricting to your IP
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "diavgeia-mq-sg"
  }
}

# RDS PostgreSQL with pgvector support
resource "aws_db_instance" "postgres" {
  identifier = "diavgeia-dev-postgres"
  
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.rds_instance_class
  
  allocated_storage     = var.rds_allocated_storage
  max_allocated_storage = var.rds_max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  
  skip_final_snapshot       = true
  publicly_accessible       = true
  backup_retention_period   = 0  # Disable backups for dev
  deletion_protection       = false
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  # Enable pgvector extension
  parameter_group_name = aws_db_parameter_group.postgres.name
  
  tags = {
    Name        = "diavgeia-dev-postgres"
    Environment = "development"
  }
}

# Parameter group for pgvector
resource "aws_db_parameter_group" "postgres" {
  family = "postgres15"
  name   = "diavgeia-postgres-params"

  parameter {
    name  = "shared_preload_libraries"
    value = "vector"
  }

  tags = {
    Name = "diavgeia-postgres-params"
  }
}

# ElastiCache Redis
resource "aws_elasticache_subnet_group" "redis" {
  name       = "diavgeia-redis-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "diavgeia-redis"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = {
    Name        = "diavgeia-dev-redis"
    Environment = "development"
  }
}

# OpenSearch Domain
resource "aws_opensearch_domain" "opensearch" {
  domain_name    = "diavgeia-dev"
  engine_version = "OpenSearch_2.3"

  cluster_config {
    instance_type  = var.opensearch_instance_type
    instance_count = 1
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.opensearch_volume_size
  }

  vpc_options {
    security_group_ids = [aws_security_group.opensearch.id]
    subnet_ids         = [data.aws_subnets.default.ids[0]]
  }

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "es:*"
        Principal = "*"
        Effect = "Allow"
        Resource = "arn:aws:es:${var.aws_region}:*:domain/diavgeia-dev/*"
      }
    ]
  })

  advanced_security_options {
    enabled = false
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https = true
  }

  tags = {
    Name        = "diavgeia-dev-opensearch"
    Environment = "development"
  }
}

# Amazon MQ (RabbitMQ)
resource "aws_mq_broker" "rabbitmq" {
  broker_name = "diavgeia-rabbitmq"
  
  configuration {
    id       = aws_mq_configuration.rabbitmq.id
    revision = aws_mq_configuration.rabbitmq.latest_revision
  }
  
  engine_type    = "RabbitMQ"
  engine_version = "3.12.13"
  instance_type  = var.mq_instance_type
  
  security_groups = [aws_security_group.mq.id]
  subnet_ids      = [data.aws_subnets.default.ids[0]]
  
  publicly_accessible = true
  
  user {
    username = var.mq_username
    password = var.mq_password
  }

  tags = {
    Name        = "diavgeia-dev-rabbitmq"
    Environment = "development"
  }
}

resource "aws_mq_configuration" "rabbitmq" {
  description    = "Diavgeia RabbitMQ Configuration"
  name           = "diavgeia-rabbitmq-config"
  engine_type    = "RabbitMQ"
  engine_version = "3.12.13"

  data = <<DATA
# Default RabbitMQ delivery acknowledgement timeout is 30 minutes in milliseconds
consumer_timeout = 1800000
DATA
}
