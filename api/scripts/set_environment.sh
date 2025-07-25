#!/bin/bash

# Script to switch between different Neo4j environments

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_NO_ADC=10
readonly EXIT_SECRET_RESOLUTION_FAILED=11
readonly EXIT_PYTHON_NOT_FOUND=12
readonly EXIT_ENV_FILE_NOT_FOUND=13

# Constants
readonly ADC_CHECK_SCRIPT="scripts/check_adc.py"
readonly RESOLVE_SECRETS_SCRIPT="scripts/resolve_secrets.py"
readonly SECRET_RESOLUTION_TIMEOUT=10

# Helper function to check if ADC is configured
is_adc_configured() {
    if command -v uv &> /dev/null; then
        uv run python "$ADC_CHECK_SCRIPT" 2>/dev/null
    elif command -v python3 &> /dev/null; then
        python3 "$ADC_CHECK_SCRIPT" 2>/dev/null
    else
        return 1
    fi
}

# Helper function to get the appropriate timeout command
get_timeout_command() {
    if command -v gtimeout &> /dev/null; then
        echo "gtimeout"
    elif command -v timeout &> /dev/null; then
        echo "timeout"
    else
        echo ""
    fi
}

# Helper function to get the appropriate Python command
get_python_command() {
    if command -v uv &> /dev/null; then
        echo "uv run python"
    elif command -v python3 &> /dev/null; then
        echo "python3"
    else
        echo ""
    fi
}

# Helper function to run secret resolution with timeout
run_secret_resolution() {
    local env_file=$1
    local python_cmd=$2
    local timeout_cmd=$3
    local temp_output=$4
    
    # Add debug mode
    if [ -n "$DEBUG_SECRETS" ]; then
        echo "DEBUG: Running: $timeout_cmd ${SECRET_RESOLUTION_TIMEOUT}s $python_cmd $RESOLVE_SECRETS_SCRIPT $env_file"
    fi
    
    # Always run with timeout (timeout_cmd is guaranteed to exist by caller)
    $timeout_cmd ${SECRET_RESOLUTION_TIMEOUT}s $python_cmd "$RESOLVE_SECRETS_SCRIPT" "$env_file" 2>&1 | tee "$temp_output"
}

# Helper function to create a timestamped backup
create_backup() {
    if [ -f .env ]; then
        local backup_name=".env.backup.$(date +%Y%m%d_%H%M%S)"
        cp .env "$backup_name"
        echo "$backup_name"
    else
        echo ""
    fi
}

# Helper function to clean up old backups (keep only the 5 most recent)
cleanup_old_backups() {
    local backup_count=$(ls -1 .env.backup.* 2>/dev/null | wc -l)
    if [ "$backup_count" -gt 5 ]; then
        # Remove all but the 5 most recent backups
        ls -1t .env.backup.* 2>/dev/null | tail -n +6 | xargs rm -f
        echo "🧹 Cleaned up old backup files"
    fi
}

# Helper function to check if env file contains secrets
has_secret_references() {
    local env_file=$1
    grep -q "projects/.*/secrets/.*/versions/" "$env_file" 2>/dev/null
}

# Function to check and resolve secrets
resolve_secrets() {
    local env_file=$1
    
    # Check if the env file has any secrets
    if ! has_secret_references "$env_file"; then
        echo "ℹ️  No Google Secret Manager references found in $env_file"
        return $EXIT_SUCCESS
    fi
    
    echo "🔐 Checking Google Cloud credentials..."
    
    # Check if ADC is configured
    if ! is_adc_configured; then
        echo "❌ ERROR: Google Cloud Application Default Credentials not found."
        echo "   Secret resolution is required for proper environment setup."
        echo ""
        echo "   To authenticate, run:"
        echo "   gcloud auth application-default login"
        echo ""
        echo "   If you don't have gcloud CLI installed, get it from:"
        echo "   https://cloud.google.com/sdk/docs/install"
        return $EXIT_NO_ADC
    fi
    
    # Get Python command
    local python_cmd=$(get_python_command)
    if [ -z "$python_cmd" ]; then
        echo "❌ ERROR: Python not found. Cannot resolve secrets."
        echo "   Please ensure Python is installed."
        return $EXIT_PYTHON_NOT_FOUND
    fi
    
    # Get timeout command
    local timeout_cmd=$(get_timeout_command)
    if [ -z "$timeout_cmd" ]; then
        echo "❌ ERROR: Timeout command not found. Cannot safely resolve secrets."
        echo "   Secret resolution requires timeout protection to prevent hanging."
        echo ""
        echo "   To fix this:"
        echo "   - On macOS: brew install coreutils"
        echo "   - On Linux: timeout should be available by default"
        return $EXIT_SECRET_RESOLUTION_FAILED
    fi
    
    echo "🔐 Resolving secrets from Google Secret Manager..."
    
    # Create a temporary file to capture the output
    local temp_output=$(mktemp)
    local resolution_exit_code=0
    
    # Run secret resolution
    run_secret_resolution "$env_file" "$python_cmd" "$timeout_cmd" "$temp_output"
    resolution_exit_code=$?
    
    # Check if resolution was successful
    local success=false
    if [ $resolution_exit_code -eq 0 ] && grep -q "✅ Resolved" "$temp_output"; then
        success=true
    fi
    
    # Clean up temp file
    rm -f "$temp_output"
    
    if [ "$success" = false ]; then
        echo ""
        echo "❌ ERROR: Failed to resolve secrets from Google Secret Manager."
        echo "   This may be due to:"
        echo "   - Expired ADC credentials (run: gcloud auth application-default login)"
        echo "   - Missing IAM permissions for Secret Manager"
        echo "   - Network connectivity issues"
        echo "   - Incorrect project configuration"
        echo ""
        echo "   The environment was NOT fully configured."
        return $EXIT_SECRET_RESOLUTION_FAILED
    fi
    
    return $EXIT_SUCCESS
}

if [ $# -eq 0 ]; then
    echo "Usage: ./set_environment.sh [development|staging|production]"
    if [ -f .env ]; then
        current_env=$(grep ENVIRONMENT .env 2>/dev/null | cut -d'=' -f2)
        echo "Current environment: ${current_env:-'not set'}"
    else
        echo "Current environment: not set"
    fi
    exit 1
fi

ENV=$1

case $ENV in
    development|dev)
        if [ ! -f .env.development ]; then
            echo "❌ ERROR: .env.development file not found"
            exit $EXIT_ENV_FILE_NOT_FOUND
        fi
        
        # Create timestamped backup
        backup_file=$(create_backup)
        if [ -n "$backup_file" ]; then
            echo "📦 Created backup: $backup_file"
        fi
        
        # Copy new environment file
        cp .env.development .env
        echo "✅ Switched to DEVELOPMENT environment"
        echo "   Neo4j: Development Aura instance"
        echo "   Debug: Enabled"
        
        # Resolve secrets
        resolve_secrets .env.development
        secret_exit_code=$?
        
        if [ $secret_exit_code -ne 0 ]; then
            echo ""
            echo "❌ Environment setup failed (exit code: $secret_exit_code)"
            
            # Revert to backup if it exists
            if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
                echo "   Reverting to previous .env file..."
                mv "$backup_file" .env
            else
                echo "   Removing incomplete .env file..."
                rm -f .env
            fi
            
            exit $secret_exit_code
        fi
        
        # Clean up backup on success
        if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
            rm -f "$backup_file"
        fi
        
        # Clean up old backups
        cleanup_old_backups
        ;;
    staging|stage)
        if [ ! -f .env.staging ]; then
            echo "❌ ERROR: .env.staging file not found"
            exit $EXIT_ENV_FILE_NOT_FOUND
        fi
        
        # Create timestamped backup
        backup_file=$(create_backup)
        if [ -n "$backup_file" ]; then
            echo "📦 Created backup: $backup_file"
        fi
        
        # Copy new environment file
        cp .env.staging .env
        echo "✅ Switched to STAGING environment"
        echo "   Neo4j: Staging Aura instance"
        echo "   Debug: Disabled"
        
        # Resolve secrets
        resolve_secrets .env.staging
        secret_exit_code=$?
        
        if [ $secret_exit_code -ne 0 ]; then
            echo ""
            echo "❌ Environment setup failed (exit code: $secret_exit_code)"
            
            # Revert to backup if it exists
            if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
                echo "   Reverting to previous .env file..."
                mv "$backup_file" .env
            else
                echo "   Removing incomplete .env file..."
                rm -f .env
            fi
            
            exit $secret_exit_code
        fi
        
        # Clean up backup on success
        if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
            rm -f "$backup_file"
        fi
        
        # Clean up old backups
        cleanup_old_backups
        ;;
    production|prod)
        if [ ! -f .env.production ]; then
            echo "❌ ERROR: .env.production file not found"
            exit $EXIT_ENV_FILE_NOT_FOUND
        fi
        
        # Create timestamped backup
        backup_file=$(create_backup)
        if [ -n "$backup_file" ]; then
            echo "📦 Created backup: $backup_file"
        fi
        
        # Copy new environment file
        cp .env.production .env
        echo "⚠️  Switched to PRODUCTION environment"
        echo "   Neo4j: Production Aura instance"
        echo "   Debug: Disabled"
        echo "   WARNING: You are now connected to PRODUCTION!"
        
        # Resolve secrets
        resolve_secrets .env.production
        secret_exit_code=$?
        
        if [ $secret_exit_code -ne 0 ]; then
            echo ""
            echo "❌ Environment setup failed (exit code: $secret_exit_code)"
            
            # Revert to backup if it exists
            if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
                echo "   Reverting to previous .env file..."
                mv "$backup_file" .env
            else
                echo "   Removing incomplete .env file..."
                rm -f .env
            fi
            
            exit $secret_exit_code
        fi
        
        # Clean up backup on success
        if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
            rm -f "$backup_file"
        fi
        
        # Clean up old backups
        cleanup_old_backups
        ;;
    *)
        echo "❌ Invalid environment: $ENV"
        echo "   Valid options: development, staging, production"
        exit 1
        ;;
esac

# Show current Neo4j URI, Google Cloud Project, and reCAPTCHA status
echo "   Neo4j URI: $(grep NEO4J_URI .env | cut -d'=' -f2)"
echo "   GCP Project: $(grep GOOGLE_CLOUD_PROJECT_ID .env | cut -d'=' -f2)"
echo "   reCAPTCHA: $([ -n "$(grep RECAPTCHA_SITE_KEY .env | cut -d'=' -f2)" ] && echo 'Configured' || echo 'Not configured')"