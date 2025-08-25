#!/bin/bash

# KEN-E Redis Deployment Script
# This script deploys Google Cloud Memorystore for Redis using Terraform

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"
VARS_FILE="${TERRAFORM_DIR}/vars/env.tfvars"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install Terraform first."
        exit 1
    fi
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install Google Cloud SDK first."
        exit 1
    fi
    
    # Check if user is authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "."; then
        log_error "You are not authenticated with gcloud. Please run 'gcloud auth login'."
        exit 1
    fi
    
    # Check if Terraform directory exists
    if [ ! -d "$TERRAFORM_DIR" ]; then
        log_error "Terraform directory not found: $TERRAFORM_DIR"
        exit 1
    fi
    
    # Check if variables file exists
    if [ ! -f "$VARS_FILE" ]; then
        log_error "Variables file not found: $VARS_FILE"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Initialize Terraform
init_terraform() {
    log_info "Initializing Terraform..."
    
    cd "$TERRAFORM_DIR"
    
    if terraform init; then
        log_success "Terraform initialized successfully"
    else
        log_error "Failed to initialize Terraform"
        exit 1
    fi
}

# Plan deployment
plan_deployment() {
    log_info "Creating Terraform plan..."
    
    cd "$TERRAFORM_DIR"
    
    if terraform plan -var-file="$VARS_FILE" -out=redis.tfplan; then
        log_success "Terraform plan created successfully"
        echo ""
        log_info "Review the plan above before proceeding with deployment."
        echo ""
    else
        log_error "Failed to create Terraform plan"
        exit 1
    fi
}

# Apply deployment
apply_deployment() {
    log_info "Applying Terraform configuration..."
    
    cd "$TERRAFORM_DIR"
    
    if terraform apply redis.tfplan; then
        log_success "Terraform apply completed successfully"
    else
        log_error "Failed to apply Terraform configuration"
        exit 1
    fi
}

# Get deployment outputs
get_outputs() {
    log_info "Retrieving deployment outputs..."
    
    cd "$TERRAFORM_DIR"
    
    echo ""
    log_info "Redis Connection Information:"
    echo "=============================="
    
    # Get staging outputs
    if terraform output staging_redis_host &> /dev/null; then
        STAGING_HOST=$(terraform output -raw staging_redis_host)
        STAGING_PORT=$(terraform output -raw staging_redis_port)
        STAGING_AUTH_SECRET=$(terraform output -raw staging_redis_auth_secret)
        
        echo ""
        log_success "Staging Redis:"
        echo "  Host: $STAGING_HOST"
        echo "  Port: $STAGING_PORT"
        echo "  Auth Secret: projects/ken-e-staging/secrets/$STAGING_AUTH_SECRET/versions/latest"
    else
        log_warning "Could not retrieve staging Redis outputs"
    fi
    
    # Get production outputs
    if terraform output prod_redis_host &> /dev/null; then
        PROD_HOST=$(terraform output -raw prod_redis_host)
        PROD_PORT=$(terraform output -raw prod_redis_port)
        PROD_AUTH_SECRET=$(terraform output -raw prod_redis_auth_secret)
        
        echo ""
        log_success "Production Redis:"
        echo "  Host: $PROD_HOST"
        echo "  Port: $PROD_PORT"
        echo "  Auth Secret: projects/ken-e-production/secrets/$PROD_AUTH_SECRET/versions/latest"
    else
        log_warning "Could not retrieve production Redis outputs"
    fi
    
    echo ""
}

# Update Cloud Build configurations
update_cloud_build() {
    log_info "Next steps to complete Redis integration:"
    echo ""
    echo "1. Update Cloud Build configuration files:"
    echo "   - Update deployment/cd/staging.yaml with Redis environment variables"
    echo "   - Update deployment/cd/deploy-to-prod.yaml with Redis environment variables"
    echo ""
    echo "2. Update API environment files:"
    echo "   - Update api/.env.staging with Redis connection details"
    echo "   - Update api/.env.production with Redis connection details"
    echo ""
    echo "3. Test Redis connection:"
    echo "   - Run: cd api && uv run -- python scripts/test_redis_connection.py"
    echo ""
    echo "4. Deploy updated API with Redis support:"
    echo "   - Commit changes and push to trigger CI/CD pipeline"
    echo ""
}

# Verify Redis instances
verify_instances() {
    log_info "Verifying Redis instances..."
    
    echo ""
    log_info "Staging Redis instance:"
    if gcloud redis instances describe kene-redis-staging --region=us-central1 --project=ken-e-staging --format="value(state)" 2>/dev/null | grep -q "READY"; then
        log_success "Staging Redis instance is READY"
    else
        log_warning "Staging Redis instance is not ready yet (this may take a few minutes)"
    fi
    
    echo ""
    log_info "Production Redis instance:"
    if gcloud redis instances describe kene-redis-prod --region=us-central1 --project=ken-e-production --format="value(state)" 2>/dev/null | grep -q "READY"; then
        log_success "Production Redis instance is READY"
    else
        log_warning "Production Redis instance is not ready yet (this may take a few minutes)"
    fi
    
    echo ""
}

# Set up monitoring
setup_monitoring() {
    log_info "Setting up monitoring and alerting..."
    
    # Create monitoring dashboard
    log_info "Creating Redis monitoring dashboard..."
    if gcloud monitoring dashboards create --config-from-file="${SCRIPT_DIR}/../monitoring/redis-dashboard.json" --project=ken-e-staging 2>/dev/null; then
        log_success "Monitoring dashboard created for staging"
    else
        log_warning "Could not create monitoring dashboard (may already exist)"
    fi
    
    # Create alert policies
    log_info "Creating alert policies..."
    if gcloud alpha monitoring policies create --policy-from-file="${SCRIPT_DIR}/../monitoring/redis-memory-alert.yaml" --project=ken-e-staging 2>/dev/null; then
        log_success "Memory alert policy created for staging"
    else
        log_warning "Could not create memory alert policy (may already exist)"
    fi
    
    if gcloud alpha monitoring policies create --policy-from-file="${SCRIPT_DIR}/../monitoring/redis-availability-alert.yaml" --project=ken-e-staging 2>/dev/null; then
        log_success "Availability alert policy created for staging"
    else
        log_warning "Could not create availability alert policy (may already exist)"
    fi
    
    log_info "Repeat monitoring setup for production project as needed"
    echo ""
}

# Main deployment function
deploy() {
    echo "🚀 KEN-E Redis Deployment"
    echo "========================="
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Initialize Terraform
    init_terraform
    
    # Create deployment plan
    plan_deployment
    
    # Confirm deployment
    echo ""
    read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Apply deployment
        apply_deployment
        
        # Get outputs
        get_outputs
        
        # Verify instances
        verify_instances
        
        # Set up monitoring
        setup_monitoring
        
        # Show next steps
        update_cloud_build
        
        log_success "Redis deployment completed successfully!"
        
    else
        log_info "Deployment cancelled by user"
        # Clean up plan file
        cd "$TERRAFORM_DIR"
        rm -f redis.tfplan
    fi
}

# Show usage
usage() {
    echo "KEN-E Redis Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy      Deploy Redis instances (default)"
    echo "  plan        Create deployment plan only"
    echo "  outputs     Show deployment outputs"
    echo "  verify      Verify Redis instances status"
    echo "  monitor     Set up monitoring and alerting"
    echo "  help        Show this help message"
    echo ""
}

# Handle command line arguments
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "plan")
        check_prerequisites
        init_terraform
        plan_deployment
        ;;
    "outputs")
        check_prerequisites
        cd "$TERRAFORM_DIR"
        get_outputs
        ;;
    "verify")
        verify_instances
        ;;
    "monitor")
        setup_monitoring
        ;;
    "help"|"-h"|"--help")
        usage
        ;;
    *)
        log_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac