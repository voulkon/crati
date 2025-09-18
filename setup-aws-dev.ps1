#!/usr/bin/env powershell

# AWS Ultra-Light Development Setup Script
# This script automates the setup process

param(
    [switch]$Deploy,
    [switch]$Destroy,
    [switch]$Status,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"

function Show-Help {
    Write-Host @"
AWS Ultra-Light Development Setup

Usage:
    .\setup-aws-dev.ps1 -Deploy    # Deploy AWS infrastructure
    .\setup-aws-dev.ps1 -Destroy   # Destroy AWS infrastructure
    .\setup-aws-dev.ps1 -Status    # Show infrastructure status
    .\setup-aws-dev.ps1 -Start     # Start local development containers
    .\setup-aws-dev.ps1 -Stop      # Stop local development containers
    .\setup-aws-dev.ps1 -Logs      # Show container logs

Prerequisites:
    - AWS CLI configured
    - Terraform installed
    - Docker installed
"@
}

function Test-Prerequisites {
    Write-Host "Checking prerequisites..." -ForegroundColor Yellow
    
    # Check AWS CLI
    try {
        aws sts get-caller-identity | Out-Null
        Write-Host "✓ AWS CLI configured" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ AWS CLI not configured. Run 'aws configure'" -ForegroundColor Red
        exit 1
    }
    
    # Check Terraform
    try {
        terraform version | Out-Null
        Write-Host "✓ Terraform installed" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ Terraform not installed" -ForegroundColor Red
        exit 1
    }
    
    # Check Docker
    try {
        docker version | Out-Null
        Write-Host "✓ Docker running" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ Docker not running" -ForegroundColor Red
        exit 1
    }
}

function Deploy-Infrastructure {
    Write-Host "Deploying AWS infrastructure..." -ForegroundColor Yellow
    
    Set-Location terraform
    
    # Check if terraform.tfvars exists
    if (-not (Test-Path "terraform.tfvars")) {
        Write-Host "Creating terraform.tfvars from example..." -ForegroundColor Yellow
        Copy-Item "terraform.tfvars.example" "terraform.tfvars"
        Write-Host "Please edit terraform/terraform.tfvars with your settings, then run this script again." -ForegroundColor Red
        exit 1
    }
    
    # Initialize and apply
    terraform init
    terraform plan
    
    $confirm = Read-Host "Do you want to apply these changes? (yes/no)"
    if ($confirm -eq "yes") {
        terraform apply -auto-approve
        
        Write-Host "`nDeployment complete! Getting connection details..." -ForegroundColor Green
        terraform output -json env_vars | ConvertFrom-Json | ConvertTo-Json -Depth 10
        
        Write-Host "`nNext steps:" -ForegroundColor Yellow
        Write-Host "1. Copy the above values to .env_files\.env.aws.secrets"
        Write-Host "2. Run: .\setup-aws-dev.ps1 -Start"
    }
    
    Set-Location ..
}

function Destroy-Infrastructure {
    Write-Host "Destroying AWS infrastructure..." -ForegroundColor Yellow
    
    Set-Location terraform
    
    $confirm = Read-Host "This will destroy ALL AWS resources. Are you sure? (yes/no)"
    if ($confirm -eq "yes") {
        terraform destroy -auto-approve
        Write-Host "Infrastructure destroyed." -ForegroundColor Green
    }
    
    Set-Location ..
}

function Show-Status {
    Write-Host "Infrastructure status:" -ForegroundColor Yellow
    
    Set-Location terraform
    terraform output
    Set-Location ..
    
    Write-Host "`nLocal containers status:" -ForegroundColor Yellow
    docker-compose -f docker\docker-compose.aws.yml ps
}

function Start-Development {
    Write-Host "Starting ultra-light development environment..." -ForegroundColor Yellow
    
    if (-not (Test-Path ".env_files\.env.aws.secrets")) {
        Write-Host "Please create .env_files\.env.aws.secrets with your AWS connection details" -ForegroundColor Red
        exit 1
    }
    
    docker-compose -f docker\docker-compose.aws.yml up -d --build
    
    Write-Host "Development environment started!" -ForegroundColor Green
    Write-Host "Backend: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "Worker Debug: http://localhost:8004" -ForegroundColor Cyan
}

function Stop-Development {
    Write-Host "Stopping development environment..." -ForegroundColor Yellow
    docker-compose -f docker\docker-compose.aws.yml down
    Write-Host "Development environment stopped." -ForegroundColor Green
}

function Show-Logs {
    docker-compose -f docker\docker-compose.aws.yml logs -f
}

# Main script logic
if (-not $Deploy -and -not $Destroy -and -not $Status -and -not $Start -and -not $Stop -and -not $Logs) {
    Show-Help
    exit 0
}

Test-Prerequisites

if ($Deploy) { Deploy-Infrastructure }
if ($Destroy) { Destroy-Infrastructure }
if ($Status) { Show-Status }
if ($Start) { Start-Development }
if ($Stop) { Stop-Development }
if ($Logs) { Show-Logs }
