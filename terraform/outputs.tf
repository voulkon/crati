output "database_url" {
  description = "PostgreSQL connection URL"
  value       = "postgres://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}"
  sensitive   = true
}

output "database_host" {
  description = "PostgreSQL host"
  value       = aws_db_instance.postgres.address
}

output "database_port" {
  description = "PostgreSQL port"
  value       = aws_db_instance.postgres.port
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].port
}

output "opensearch_endpoint" {
  description = "OpenSearch endpoint"
  value       = "https://${aws_opensearch_domain.opensearch.endpoint}"
}

output "opensearch_dashboards_endpoint" {
  description = "OpenSearch Dashboards endpoint"
  value       = "https://${aws_opensearch_domain.opensearch.dashboard_endpoint}"
}

output "rabbitmq_endpoint" {
  description = "RabbitMQ endpoint"
  value       = "amqps://${var.mq_username}:${var.mq_password}@${aws_mq_broker.rabbitmq.instances[0].endpoints[0]}"
  sensitive   = true
}

output "rabbitmq_management_url" {
  description = "RabbitMQ Management Console URL"
  value       = "https://${aws_mq_broker.rabbitmq.instances[0].console_url}"
}

# Environment variables for easy copy-paste
output "env_vars" {
  description = "Environment variables for .env file"
  value = {
    DATABASE_URL       = "postgres://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}"
    REDIS_HOST         = aws_elasticache_cluster.redis.cache_nodes[0].address
    REDIS_PORT         = aws_elasticache_cluster.redis.cache_nodes[0].port
    OPENSEARCH_URL     = "https://${aws_opensearch_domain.opensearch.endpoint}"
    CELERY_BROKER_URL  = "amqps://${var.mq_username}:${var.mq_password}@${aws_mq_broker.rabbitmq.instances[0].endpoints[0]}"
  }
  sensitive = true
}
