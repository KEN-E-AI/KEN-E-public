#!/bin/bash

# Docker management scripts for Kene API

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_section() {
    echo -e "${BLUE}==== $1 ====${NC}"
}

# Development commands
dev_build() {
    print_section "Building development image"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml build
}

dev_up() {
    print_section "Starting development environment"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    print_status "Development server available at http://localhost:8000"
    print_status "API docs available at http://localhost:8000/docs"
}

dev_down() {
    print_section "Stopping development environment"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml down
}

dev_logs() {
    print_section "Showing development logs"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f api
}

# Production commands
prod_build() {
    print_section "Building production image"
    docker-compose -f docker-compose.prod.yml build
}

prod_up() {
    print_section "Starting production environment"
    docker-compose -f docker-compose.prod.yml up -d
    print_status "Production server available at http://localhost"
    print_status "API docs available at http://localhost/docs"
}

prod_down() {
    print_section "Stopping production environment"
    docker-compose -f docker-compose.prod.yml down
}

prod_logs() {
    print_section "Showing production logs"
    docker-compose -f docker-compose.prod.yml logs -f
}

# Testing commands
test() {
    print_section "Running tests in Docker"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml exec api uv run pytest tests/ -v
}

# Utility commands
clean() {
    print_section "Cleaning up Docker resources"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans
    docker-compose -f docker-compose.prod.yml down -v --remove-orphans
    docker system prune -f
}

health() {
    print_section "Checking API health"
    curl -f http://localhost:8000/health || curl -f http://localhost/health
}

# Help function
show_help() {
    echo "Kene API Docker Management Script"
    echo ""
    echo "Development commands:"
    echo "  dev:build    - Build development Docker image"
    echo "  dev:up       - Start development environment"
    echo "  dev:down     - Stop development environment"
    echo "  dev:logs     - Show development logs"
    echo ""
    echo "Production commands:"
    echo "  prod:build   - Build production Docker image"
    echo "  prod:up      - Start production environment"
    echo "  prod:down    - Stop production environment"
    echo "  prod:logs    - Show production logs"
    echo ""
    echo "Testing commands:"
    echo "  test         - Run tests in Docker container"
    echo ""
    echo "Utility commands:"
    echo "  clean        - Clean up Docker resources"
    echo "  health       - Check API health"
    echo "  help         - Show this help message"
}

# Main command dispatcher
case "${1}" in
    "dev:build")
        dev_build
        ;;
    "dev:up")
        dev_up
        ;;
    "dev:down")
        dev_down
        ;;
    "dev:logs")
        dev_logs
        ;;
    "prod:build")
        prod_build
        ;;
    "prod:up")
        prod_up
        ;;
    "prod:down")
        prod_down
        ;;
    "prod:logs")
        prod_logs
        ;;
    "test")
        test
        ;;
    "clean")
        clean
        ;;
    "health")
        health
        ;;
    "help"|"--help"|"-h"|"")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
