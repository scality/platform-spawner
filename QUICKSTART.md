# Quick Start Guide

Deploy your first cluster in 5 minutes.

## Step 1: Install Dependencies

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install packages
uv pip install -r requirements.txt
```

## Step 2: Get Scaleway Credentials

1. Visit [Scaleway Console](https://console.scaleway.com/)
2. Go to **IAM** → **API Keys** → **Generate API Key**
3. Copy **Access Key** and **Secret Key**
4. Note your **Project ID** from project settings

## Step 3: Configure Stack

```bash
# Initialize stack
pulumi stack init dev

# Set required configuration
pulumi config set project_id YOUR_PROJECT_ID
pulumi config set worker_count 1
pulumi config set name_prefix dev

# Set credentials (encrypted)
pulumi config set --secret scaleway:access_key YOUR_ACCESS_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET_KEY
```

## Step 4: Deploy

```bash
# Preview changes
pulumi preview

# Deploy infrastructure
pulumi up

# View gateway IP
pulumi stack output gateway_bastion_ip
```

## Step 5: Access Your Nodes

```bash
# Get SSH command for first node
pulumi stack output nodes --json | jq -r '."dev-node-01".ssh_command'

# Connect to node
ssh -J bastion@<gateway_ip>:61000 artesca-os@dev-node-01.dev-internal.internal
```

## Configuration Examples

### Single Node (Development)

```bash
worker_count: 1
name_prefix: dev
instance_type: PLAY2-MICRO
```

Resources created: `dev-node-01`, `dev-vpc`, `dev-gateway`

### 3 Workers (Staging)

```bash
worker_count: 3
name_prefix: staging
instance_type: PRO2-S
```

Resources created: `staging-node-01/02/03`, `staging-vpc`, `staging-gateway`

### 6 Workers (Production)

```bash
worker_count: 6
name_prefix: prod
instance_type: PRO2-M
worker_snapshot_id: YOUR_SNAPSHOT_ID
```

Resources created: `prod-node-01` through `prod-node-06`, `prod-vpc`, `prod-gateway`

## Quick Reference

### Common Commands

```bash
# Deploy
pulumi up

# View outputs
pulumi stack output --json
pulumi stack output gateway_bastion_ip

# Get SSH commands
pulumi stack output nodes --json | jq -r '.[] | .ssh_command'

# Destroy
pulumi destroy
```

### Configuration

```bash
# View all config
pulumi config

# Set configuration
pulumi config set KEY VALUE
pulumi config set --secret KEY VALUE

# Remove configuration
pulumi config rm KEY
```

### Stacks

```bash
# List stacks
pulumi stack ls

# Create stack
pulumi stack init STACK_NAME

# Switch stack
pulumi stack select STACK_NAME
```

## Next Steps

- Change worker count: `pulumi config set worker_count 6`
- Add name prefix: `pulumi config set name_prefix prod`
- Use custom image: `pulumi config set worker_snapshot_id YOUR_ID`
- Add volumes: `pulumi config set additional_volumes '[{"suffix":"data","size":100}]'`
- Read full documentation: [README.md](README.md)

## Common Issues

**Authentication fails:**
```bash
pulumi config set --secret scaleway:access_key YOUR_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET
```

**Wrong instance type:**
```bash
# Check available types: PLAY2-MICRO, PRO2-S, PRO2-M, PRO2-L
pulumi config set instance_type PRO2-S
```

**Image not found:**
```bash
# Use marketplace image
pulumi config rm worker_snapshot_id
```

## Production Checklist

Before deploying to production:

- [ ] Set worker_count appropriately
- [ ] Use production instance type (`PRO2-S` or higher)
- [ ] Set name_prefix for organization
- [ ] Use custom snapshot with your software
- [ ] Configure additional volumes if needed
- [ ] Test in staging first
- [ ] Set up monitoring
- [ ] Document your configuration

## Get Help

- Full documentation: [README.md](README.md)
- Pulumi docs: https://www.pulumi.com/docs/
- Scaleway docs: https://www.scaleway.com/en/docs/
