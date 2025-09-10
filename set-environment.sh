#!/bin/bash

# Unified Environment Switching Script for KEN-E
# This script switches the environment for all three components:
# 1. Agents (app/adk)
# 2. API
# 3. Frontend

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the root directory
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print section headers
print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Function to check if a file exists
check_file() {
    if [ ! -f "$1" ]; then
        print_error "File not found: $1"
        return 1
    fi
    return 0
}

# Function to switch agents environment
switch_agents_env() {
    local env=$1
    local agents_dir="$ROOT_DIR/app/adk"
    
    print_section "STEP 1: Configuring Agents Environment"
    
    # Check if source env file exists
    local env_file="$agents_dir/.env.$env"
    if ! check_file "$env_file"; then
        return 1
    fi
    
    # Copy the environment file
    cp "$env_file" "$agents_dir/.env"
    
    print_success "Agents environment switched to $env"
    print_info "  Source: $env_file"
    print_info "  Target: $agents_dir/.env"
    
    # Show key configuration values
    local project_id=$(grep "^GOOGLE_CLOUD_PROJECT_ID=" "$agents_dir/.env" | cut -d'=' -f2)
    print_info "  Project ID: $project_id"
    
    return 0
}

# Function to switch API environment
switch_api_env() {
    local env=$1
    local api_dir="$ROOT_DIR/api"
    
    print_section "STEP 2: Configuring API Environment"
    
    # Check if the set_environment_with_sa.sh script exists
    local api_script="$api_dir/scripts/set_environment_with_sa.sh"
    if ! check_file "$api_script"; then
        print_warning "API script not found, trying alternative method..."
        
        # Alternative: directly copy the env file
        local env_file="$api_dir/.env.$env"
        if check_file "$env_file"; then
            cp "$env_file" "$api_dir/.env"
            print_success "API environment switched to $env (direct copy)"
            return 0
        else
            return 1
        fi
    fi
    
    # Run the API environment script
    cd "$api_dir"
    bash "$api_script" "$env" > /tmp/api_env_switch.log 2>&1
    local result=$?
    
    if [ $result -eq 0 ]; then
        print_success "API environment switched to $env"
        
        # Extract and show key information from the log
        if grep -q "Service Account:" /tmp/api_env_switch.log; then
            local sa_file=$(grep "Service Account:" /tmp/api_env_switch.log | tail -1 | cut -d':' -f2 | xargs)
            print_info "  Service Account: $sa_file"
        fi
        
        # Show project ID from the env file
        if [ -f "$api_dir/.env" ]; then
            local project_id=$(grep "^GOOGLE_CLOUD_PROJECT_ID=" "$api_dir/.env" | cut -d'=' -f2)
            print_info "  Project ID: $project_id"
        fi
    else
        print_error "Failed to switch API environment"
        print_info "Check /tmp/api_env_switch.log for details"
        return 1
    fi
    
    cd "$ROOT_DIR"
    return 0
}

# Function to switch frontend environment
switch_frontend_env() {
    local env=$1
    local frontend_dir="$ROOT_DIR/frontend"
    
    print_section "STEP 3: Configuring Frontend Environment"
    
    # Check if frontend directory exists
    if [ ! -d "$frontend_dir" ]; then
        print_error "Frontend directory not found: $frontend_dir"
        return 1
    fi
    
    # Check if the environment file exists
    local env_file="$frontend_dir/.env.$env"
    if ! check_file "$env_file"; then
        return 1
    fi
    
    # Copy the environment file
    cp "$env_file" "$frontend_dir/.env"
    
    print_success "Frontend environment prepared for $env"
    print_info "  Source: $env_file"
    print_info "  Target: $frontend_dir/.env"
    
    # Show the API URL configuration
    local api_url=$(grep "^VITE_API_BASE_URL=" "$frontend_dir/.env" | cut -d'=' -f2)
    print_info "  API URL: $api_url"
    
    return 0
}

# Function to show how to start services
show_start_commands() {
    local env=$1
    
    print_section "Ready to Start Services"
    
    echo ""
    echo "You can now start the services with these commands:"
    echo ""
    echo -e "${GREEN}1. Start API:${NC}"
    echo "   cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
    echo -e "${GREEN}2. Start Frontend:${NC}"
    echo "   cd frontend && npm run dev:$env"
    echo ""
    echo -e "${GREEN}3. Run Agents (if needed):${NC}"
    echo "   cd app/adk && uv run python [your_agent_script.py]"
    echo ""
    
    if [ "$env" == "production" ]; then
        print_warning "⚠️  WARNING: You are configured for PRODUCTION environment!"
        print_warning "⚠️  Be extremely careful with any operations!"
    fi
}

# Function to validate environment name
validate_env() {
    local env=$1
    
    case $env in
        development|dev)
            echo "development"
            ;;
        staging|stage)
            echo "staging"
            ;;
        production|prod)
            echo "production"
            ;;
        *)
            return 1
            ;;
    esac
}

# Main script
main() {
    # Check if environment argument is provided
    if [ $# -eq 0 ]; then
        echo "Usage: ./set-environment.sh [development|staging|production]"
        echo ""
        echo "This script configures all three components for the specified environment:"
        echo "  • Agents (app/adk)"
        echo "  • API"
        echo "  • Frontend"
        echo ""
        echo "Available environments:"
        echo "  development (or dev)  - Local development environment"
        echo "  staging (or stage)    - Staging environment"
        echo "  production (or prod)  - Production environment (use with caution!)"
        echo ""
        
        # Try to show current environment
        if [ -f "$ROOT_DIR/api/.env" ]; then
            current_env=$(grep "^ENVIRONMENT=" "$ROOT_DIR/api/.env" 2>/dev/null | cut -d'=' -f2)
            if [ -n "$current_env" ]; then
                echo -e "${BLUE}Current environment: ${GREEN}$current_env${NC}"
            fi
        fi
        
        exit 1
    fi
    
    # Validate and normalize environment name
    ENV=$(validate_env "$1")
    if [ $? -ne 0 ]; then
        print_error "Invalid environment: $1"
        echo "Valid options: development, staging, production"
        exit 1
    fi
    
    # Print header
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║            KEN-E Unified Environment Switcher                           ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    print_info "Switching all components to: ${GREEN}${ENV}${NC} environment"
    
    # Track success
    all_success=true
    
    # Switch each component
    if ! switch_agents_env "$ENV"; then
        all_success=false
    fi
    
    if ! switch_api_env "$ENV"; then
        all_success=false
    fi
    
    if ! switch_frontend_env "$ENV"; then
        all_success=false
    fi
    
    # Final summary
    print_section "Summary"
    
    if [ "$all_success" = true ]; then
        print_success "All components successfully configured for ${GREEN}${ENV}${NC} environment!"
        show_start_commands "$ENV"
    else
        print_error "Some components failed to configure. Please check the errors above."
        exit 1
    fi
}

# Run main function
main "$@"