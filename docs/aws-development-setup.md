# AWS Ultra-Light Development Setup

This setup moves the heavy infrastructure components (PostgreSQL, Redis, OpenSearch, RabbitMQ) to AWS managed services, leaving only your application code running locally.

## Prerequisites

1. **AWS CLI** - Install and configure with your credentials
2. **Terraform** - Install Terraform CLI
3. **Docker** - For running your application locally

## Setup Steps

### 1. Configure AWS Credentials

```powershell
aws configure
```

Enter your AWS Access Key ID, Secret Access Key, and preferred region.

### 2. Setup Terraform Variables

```powershell
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your preferred settings:
- Set secure passwords for database and RabbitMQ
- Choose your AWS region
- Adjust instance sizes based on your budget

### 3. Deploy AWS Infrastructure

```powershell
# Initialize Terraform
terraform init

# Review the planned changes
terraform plan

# Deploy the infrastructure
terraform apply
```

**Note:** This will create AWS resources that may incur costs. See the cost estimation section below.

### 4. Configure Environment Variables

```powershell
# Get the connection details from Terraform
terraform output -json env_vars

# Copy the environment file template
cd ..
cp .env_files\.env.aws.secrets.example .env_files\.env.aws.secrets
```

Edit `.env_files\.env.aws.secrets` with the values from the Terraform output.

### 5. Start Your Ultra-Light Development Environment

```powershell
# Start only your application components
docker-compose -f docker\docker-compose.aws.yml up -d

# Check logs
docker-compose -f docker\docker-compose.aws.yml logs -f
```

## Quick Commands

```powershell
# Start development environment
docker-compose -f docker\docker-compose.aws.yml up -d

# Stop development environment
docker-compose -f docker\docker-compose.aws.yml down

# View logs
docker-compose -f docker\docker-compose.aws.yml logs -f

# Rebuild and restart after code changes
docker-compose -f docker\docker-compose.aws.yml up -d --build
```

## Cost Estimation (US East 1)

**Monthly costs with minimal usage:**

- **RDS PostgreSQL (db.t3.micro)**: ~$15-20/month
- **ElastiCache Redis (cache.t3.micro)**: ~$12-15/month  
- **OpenSearch (t3.small.search)**: ~$30-40/month
- **Amazon MQ RabbitMQ (mq.t3.micro)**: ~$18-25/month

**Total estimated cost: $75-100/month**

### Cost Optimization Tips

1. **Stop when not developing**: Use `terraform destroy` to tear down everything
2. **Use Spot instances**: For OpenSearch (not supported for other services)
3. **Scheduled start/stop**: Create Lambda functions to start/stop services on schedule
4. **Regional pricing**: Some regions are cheaper than US East 1

## Accessing AWS Services

After deployment, you can access:

- **RDS**: Use any PostgreSQL client with the endpoint from Terraform output
- **Redis**: Connect using redis-cli or any Redis client
- **OpenSearch**: Access via the dashboard URL from Terraform output
- **RabbitMQ**: Management console available via the URL from Terraform output

## Troubleshooting

### Connection Issues

1. **Security Groups**: Ensure your IP is allowed (current config allows all IPs)
2. **VPC**: All services are in the default VPC for simplicity
3. **SSL/TLS**: OpenSearch and RabbitMQ use HTTPS/AMQPS

### Application Issues

1. **Environment Variables**: Double-check all values in `.env.aws.secrets`
2. **Network**: Ensure your local Docker can reach AWS services
3. **Credentials**: Verify AWS credentials and permissions

### Cost Control

```powershell
# Destroy everything when not needed
terraform destroy

# Or stop specific services
aws rds stop-db-instance --db-instance-identifier diavgeia-dev-postgres
```

## Switching Back to Local Development

Simply use your original docker-compose file:

```powershell
docker-compose -f docker\docker-compose.dev.yml up -d
```

## Production Considerations

This setup is designed for development. For production:

1. **Security**: Restrict security groups to specific IPs
2. **Backups**: Enable automated backups
3. **Multi-AZ**: Enable for high availability
4. **Monitoring**: Add CloudWatch alarms
5. **Secrets**: Use AWS Secrets Manager
6. **Networking**: Use private subnets with NAT Gateway
