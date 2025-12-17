#!/usr/bin/env bash
#
# Interactive setup script for Platform Spawner
# This script helps configure a Pulumi stack with all required and optional settings
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    if [ -n "$default" ]; then
        read -p "$(echo -e ${YELLOW}?${NC}) $prompt [${GREEN}$default${NC}]: " value
        eval "$var_name=\"${value:-$default}\""
    else
        read -p "$(echo -e ${YELLOW}?${NC}) $prompt: " value
        while [ -z "$value" ]; do
            print_error "This field is required"
            read -p "$(echo -e ${YELLOW}?${NC}) $prompt: " value
        done
        eval "$var_name=\"$value\""
    fi
}

prompt_secret() {
    local prompt="$1"
    local var_name="$2"
    
    read -s -p "$(echo -e ${YELLOW}?${NC}) $prompt: " value
    echo
    while [ -z "$value" ]; do
        print_error "This field is required"
        read -s -p "$(echo -e ${YELLOW}?${NC}) $prompt: " value
        echo
    done
    eval "$var_name=\"$value\""
}

prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    
    if [ "$default" = "y" ]; then
        read -p "$(echo -e ${YELLOW}?${NC}) $prompt [${GREEN}Y/n${NC}]: " answer
        answer="${answer:-y}"
    else
        read -p "$(echo -e ${YELLOW}?${NC}) $prompt [${GREEN}y/N${NC}]: " answer
        answer="${answer:-n}"
    fi
    
    [[ "$answer" =~ ^[Yy] ]]
}

# Main setup
print_header "Platform Spawner - Interactive Setup"

echo "This script will help you configure your Pulumi stack."
echo "You can re-run this script anytime to update your configuration."
echo ""

# Check if pulumi is installed
if ! command -v pulumi &> /dev/null; then
    print_error "Pulumi CLI is not installed"
    echo "Please install Pulumi: https://www.pulumi.com/docs/get-started/install/"
    exit 1
fi

print_success "Pulumi CLI found"

# Ask if they want to create a new stack or use existing
echo ""
print_header "Stack Selection"

# List existing stacks
if pulumi stack ls &> /dev/null; then
    echo "Existing stacks:"
    pulumi stack ls
    echo ""
fi

if prompt_yes_no "Create a new stack?" "n"; then
    prompt_input "Stack name (e.g., dev, staging, prod)" "dev" STACK_NAME
    echo ""
    print_warning "Creating new stack: $STACK_NAME"
    pulumi stack init "$STACK_NAME" || {
        print_error "Failed to create stack. It may already exist."
        read -p "Use existing stack '$STACK_NAME'? [Y/n]: " answer
        answer="${answer:-y}"
        if [[ "$answer" =~ ^[Yy] ]]; then
            pulumi stack select "$STACK_NAME"
        else
            exit 1
        fi
    }
else
    prompt_input "Stack name to configure" "dev" STACK_NAME
    pulumi stack select "$STACK_NAME" || {
        print_error "Stack '$STACK_NAME' not found"
        exit 1
    }
fi

print_success "Using stack: $STACK_NAME"

# Required configuration
echo ""
print_header "Required Configuration"

echo "Get your Scaleway credentials from:"
echo "https://console.scaleway.com/iam/api-keys"
echo ""

prompt_input "Scaleway Project ID" "" PROJECT_ID
prompt_secret "Scaleway Access Key" ACCESS_KEY
prompt_secret "Scaleway Secret Key" SECRET_KEY

# Topology selection
echo ""
echo "Available topologies:"
echo "  1) single-node  - 1 worker node (development/testing)"
echo "  2) 3-nodes      - 3 worker nodes (production)"
echo "  3) 6-nodes      - 6 worker nodes (large deployments)"
echo ""
prompt_input "Select topology [1-3]" "1" TOPOLOGY_CHOICE

case $TOPOLOGY_CHOICE in
    1) TOPOLOGY="single-node" ;;
    2) TOPOLOGY="3-nodes" ;;
    3) TOPOLOGY="6-nodes" ;;
    *)
        prompt_input "Enter topology name" "single-node" TOPOLOGY
        ;;
esac

print_success "Topology: $TOPOLOGY"

# Optional configuration
echo ""
print_header "Optional Configuration"

# Region and Zone
echo "Scaleway regions:"
echo "  - fr-par (Paris): fr-par-1, fr-par-2, fr-par-3"
echo "  - nl-ams (Amsterdam): nl-ams-1, nl-ams-2"
echo "  - pl-waw (Warsaw): pl-waw-1, pl-waw-2"
echo ""
prompt_input "Region" "fr-par" REGION
prompt_input "Zone" "fr-par-1" ZONE

# Worker node configuration
echo ""
echo "Worker Node Configuration:"
echo ""

if prompt_yes_no "Use custom snapshot for worker nodes?" "n"; then
    echo ""
    echo "Find your snapshot ID at:"
    echo "https://console.scaleway.com/instance/images"
    echo ""
    prompt_input "Worker snapshot/image ID" "" WORKER_SNAPSHOT_ID
else
    WORKER_SNAPSHOT_ID=""
    echo ""
    echo "Worker nodes will use marketplace image"
    prompt_input "OS name for workers" "rockylinux" OS_NAME
    prompt_input "OS version for workers" "9" OS_VERSION
fi

# Instance type for worker nodes
echo ""
echo "Instance types for WORKER nodes:"
echo "  - PLAY2-MICRO  (4 vCPU, 4GB RAM)  - Development"
echo "  - PRO2-S       (4 vCPU, 8GB RAM)  - Production (default)"
echo "  - PRO2-M       (8 vCPU, 16GB RAM) - Production"
echo "  - PRO2-L       (16 vCPU, 32GB RAM) - Production"
echo ""
echo "Note: Gateway bastion always uses VPC-GW-S"
echo ""
prompt_input "Worker instance type" "PRO2-S" INSTANCE_TYPE

# SSH Key
echo ""
if prompt_yes_no "Add SSH public key for access?" "y"; then
    prompt_input "SSH public key" "" SSH_KEY
else
    SSH_KEY=""
fi

# Additional volumes
echo ""
if prompt_yes_no "Configure additional volumes for worker nodes?" "n"; then
    echo ""
    echo "Example: [{"suffix": "service", "size": 120}, {"suffix": "data", "size": 10, "count": 12}]"
    echo ""
    prompt_input "Additional volumes (JSON format)" "" ADDITIONAL_VOLUMES
else
    ADDITIONAL_VOLUMES=""
fi

# Apply configuration
echo ""
print_header "Applying Configuration"

echo "Setting required configuration..."
pulumi config set project_id "$PROJECT_ID"
pulumi config set topology "$TOPOLOGY"
pulumi config set --secret scaleway:access_key "$ACCESS_KEY"
pulumi config set --secret scaleway:secret_key "$SECRET_KEY"
print_success "Required configuration set"

echo ""
echo "Setting optional configuration..."
pulumi config set region "$REGION"
pulumi config set zone "$ZONE"

if [ -n "$WORKER_SNAPSHOT_ID" ]; then
    pulumi config set worker_snapshot_id "$WORKER_SNAPSHOT_ID"
    print_success "Worker snapshot ID set"
else
    pulumi config rm worker_snapshot_id 2>/dev/null || true
    pulumi config set bastion_os_name "$OS_NAME"
    pulumi config set bastion_os_version "$OS_VERSION"
    print_success "Worker OS set to marketplace image"
fi

pulumi config set instance_type "$INSTANCE_TYPE"

if [ -n "$SSH_KEY" ]; then
    pulumi config set sshPublicKey "$SSH_KEY"
    print_success "SSH key configured"
fi

if [ -n "$ADDITIONAL_VOLUMES" ]; then
    pulumi config set additional_volumes "$ADDITIONAL_VOLUMES"
    print_success "Additional volumes configured"
fi

# Summary
echo ""
print_header "Configuration Summary"

echo "Stack: $STACK_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
pulumi config
echo ""

print_success "Configuration complete!"

# Ask if they want to preview/deploy
echo ""
print_header "Next Steps"

if prompt_yes_no "Preview infrastructure changes?" "y"; then
    echo ""
    pulumi preview
fi

echo ""
if prompt_yes_no "Deploy infrastructure now?" "n"; then
    echo ""
    print_warning "Deploying infrastructure..."
    pulumi up -y
    
    echo ""
    print_success "Deployment complete!"
    echo ""
    echo "View outputs:"
    echo "  pulumi stack output --json"
    echo ""
    echo "Get gateway bastion IP:"
    echo "  pulumi stack output gateway_bastion_ip"
    echo ""
    echo "Get SSH command for node-01:"
    echo "  pulumi stack output --json | jq -r '.nodes.\"node-01\".ssh_command'"
else
    echo ""
    echo "To preview changes later:"
    echo "  ${GREEN}pulumi preview${NC}"
    echo ""
    echo "To deploy later:"
    echo "  ${GREEN}pulumi up${NC}"
fi

echo ""
print_success "Setup complete! 🚀"

