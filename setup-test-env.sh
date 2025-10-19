#!/bin/bash

# GoMama Pi MQTT Migration - Test Environment Setup
# This script sets up the complete test environment using Docker Compose

set -e

echo "🧪 GoMama Pi MQTT Migration - Test Environment Setup"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker and Docker Compose are installed
check_dependencies() {
    print_status "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Dependencies check passed"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p test-config/emqx
    mkdir -p test-data
    mkdir -p test-results
    mkdir -p logs
    
    print_success "Directories created"
}

# Create EMQX configuration
create_emqx_config() {
    print_status "Creating EMQX configuration..."
    
    cat > test-config/emqx/emqx.conf << 'EOF'
## EMQX Test Configuration

## Node name
node.name = emqx-test@127.0.0.1

## Cookie for distributed node communication
node.cookie = emqxsecretcookie

## Cluster discovery
cluster.discovery = manual

## Listeners
listeners.tcp.default.bind = 0.0.0.0:1883
listeners.tcp.default.max_connections = 1024000

listeners.ssl.default.bind = 0.0.0.0:8883
listeners.ssl.default.max_connections = 512000

listeners.ws.default.bind = 0.0.0.0:8083
listeners.ws.default.max_connections = 102400

listeners.wss.default.bind = 0.0.0.0:8084
listeners.wss.default.max_connections = 102400

## Dashboard
dashboard.listeners.http.bind = 0.0.0.0:18083
dashboard.default_username = admin
dashboard.default_password = public

## Authentication
auth.mnesia.password_hash = sha256

## Logging
log.level = info
log.dir = /opt/emqx/log
EOF

    print_success "EMQX configuration created"
}

# Stop existing containers
stop_existing() {
    print_status "Stopping existing test containers..."
    
    docker-compose -f docker-compose.test.yml down --remove-orphans || true
    
    # Remove any existing test volumes
    docker volume rm gomama_pi_mysql-test-data 2>/dev/null || true
    docker volume rm gomama_pi_redis-test-data 2>/dev/null || true
    docker volume rm gomama_pi_emqx-test-data 2>/dev/null || true
    docker volume rm gomama_pi_emqx-test-log 2>/dev/null || true
    
    print_success "Existing containers stopped"
}

# Build and start test environment
start_test_env() {
    print_status "Building and starting test environment..."
    
    # Build images
    docker-compose -f docker-compose.test.yml build
    
    # Start infrastructure services first
    print_status "Starting infrastructure services..."
    docker-compose -f docker-compose.test.yml up -d mysql-test redis-test emqx-test
    
    # Wait for services to be healthy
    print_status "Waiting for infrastructure services to be ready..."
    
    # Wait for MySQL
    print_status "Waiting for MySQL..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if docker-compose -f docker-compose.test.yml exec -T mysql-test mysqladmin ping -h localhost -u root -ptest_root_password &>/dev/null; then
            print_success "MySQL is ready"
            break
        fi
        sleep 2
        timeout=$((timeout-2))
    done
    
    if [ $timeout -le 0 ]; then
        print_error "MySQL failed to start within timeout"
        exit 1
    fi
    
    # Wait for Redis
    print_status "Waiting for Redis..."
    timeout=30
    while [ $timeout -gt 0 ]; do
        if docker-compose -f docker-compose.test.yml exec -T redis-test redis-cli -a test_redis_password ping &>/dev/null; then
            print_success "Redis is ready"
            break
        fi
        sleep 2
        timeout=$((timeout-2))
    done
    
    if [ $timeout -le 0 ]; then
        print_error "Redis failed to start within timeout"
        exit 1
    fi
    
    # Wait for EMQX
    print_status "Waiting for EMQX..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -f http://localhost:18083 &>/dev/null; then
            print_success "EMQX is ready"
            break
        fi
        sleep 2
        timeout=$((timeout-2))
    done
    
    if [ $timeout -le 0 ]; then
        print_error "EMQX failed to start within timeout"
        exit 1
    fi
    
    # Start backend service
    print_status "Starting backend service..."
    docker-compose -f docker-compose.test.yml up -d gomama-backend-test
    
    # Wait for backend
    print_status "Waiting for backend service..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -f http://localhost:9001/health &>/dev/null; then
            print_success "Backend service is ready"
            break
        fi
        sleep 2
        timeout=$((timeout-2))
    done
    
    if [ $timeout -le 0 ]; then
        print_warning "Backend service may not be ready, continuing anyway"
    fi
    
    print_success "Test environment started successfully"
}

# Display service information
show_services() {
    print_status "Test environment services:"
    echo ""
    echo "📊 EMQX Dashboard: http://localhost:18083 (admin/public)"
    echo "🐬 MySQL: localhost:3307 (gomama_test_user/test_password)"
    echo "🔴 Redis: localhost:6380 (password: test_redis_password)"
    echo "🚀 Backend API: http://localhost:9001"
    echo ""
    echo "MQTT Broker: localhost:1883"
    echo "MQTT WebSocket: localhost:8083"
    echo ""
}

# Run tests
run_tests() {
    if [ "$1" = "--run-tests" ]; then
        print_status "Running tests..."
        docker-compose -f docker-compose.test.yml up --build test-runner
    fi
}

# Start mock Pi device
start_mock_pi() {
    if [ "$1" = "--start-mock-pi" ]; then
        print_status "Starting mock Pi device..."
        docker-compose -f docker-compose.test.yml up -d mock-pi-device
        print_success "Mock Pi device started"
    fi
}

# Main execution
main() {
    check_dependencies
    create_directories
    create_emqx_config
    stop_existing
    start_test_env
    show_services
    
    # Handle command line arguments
    for arg in "$@"; do
        case $arg in
            --run-tests)
                run_tests "$arg"
                ;;
            --start-mock-pi)
                start_mock_pi "$arg"
                ;;
        esac
    done
    
    print_success "Test environment setup complete!"
    echo ""
    echo "To run tests: ./setup-test-env.sh --run-tests"
    echo "To start mock Pi: ./setup-test-env.sh --start-mock-pi"
    echo "To view logs: docker-compose -f docker-compose.test.yml logs -f [service-name]"
    echo "To stop: docker-compose -f docker-compose.test.yml down"
}

# Run main function with all arguments
main "$@"
