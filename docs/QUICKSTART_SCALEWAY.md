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

If not already done, login to Pulumi:

```bash
pulumi login --local
```

Then initialize a new stack and set required configuration:

```bash
# Initialize stack
pulumi stack init dev

# Set required configuration
pulumi config set project_id YOUR_PROJECT_ID
pulumi config set instance_count 1
pulumi config set instance_image YOUR_SNAPSHOT_ID
pulumi config set product dev

# Set credentials (encrypted)
pulumi config set --secret scaleway:access_key YOUR_ACCESS_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET_KEY
```

You need to use a specific image for the worker nodes:

```bash
pulumi config set instance_image fc979535-d07c-43b4-8c33-d8f483484d16
```
**Security Note:** By default, the gateway bastion SSH is accessible from any IP. For production, restrict access:

```bash
# Restrict to your current IP (manually edit Pulumi.<stack>.yaml)
# Or use pulumi config set with --path flag:
pulumi config set --path 'authorized_cidrs[0]' "$(curl -s https://api.ipify.org)/32"

# Or edit the stack YAML file directly to add multiple IPs:
# platform-spawner:authorized_cidrs:
#   - 1.2.3.4/32
#   - 5.6.7.0/24
```

### Extra Private Networks and Custom Routes

You can add also multiple extra private networks or custom routes if needed:

```bash
# Example: Add extra private network
pulumi config set --path 'extra_private_networks[0].suffix' data
pulumi config set --path 'extra_private_networks[0].subnet' 192.168.20.0/24
# Example: Add custom routes
pulumi config set --path 'custom_routes[0].destination' 35.241.243.135/32
pulumi config set --path 'custom_routes[0].description' artifacts.scality.net
pulumi config set --path 'custom_routes[1].destination' 217.182.187.84/32
pulumi config set --path 'custom_routes[1].description' packages.scality.com
```

### Extra Volumes

You can also add extra volumes to each node:

```bash
# Example: Add extra volume
pulumi config set --path 'extra_volumes[0].suffix' data
pulumi config set --path 'extra_volumes[0].size' 10
pulumi config set --path 'extra_volumes[0].count' 12
```

## Step 4: Deploy

**Important**: Make sure you set `product` to avoid resources being named with "unknown" prefix.

```bash
# Preview changes
pulumi preview

# Deploy infrastructure
pulumi up

# View gateway IP
pulumi stack output gateway_bastion_ip
```

This automatically configures the gateway to only accept SSH connections from the specified IP addresses.

## Step 5: Access Your Nodes

```bash
# Get SSH command for first node
pulumi stack output nodes --json | jq -r '."dev-node-01".ssh_command'

# Connect to node
ssh -J bastion@<gateway_ip>:61000 artesca-os@dev-node-01.dev-internal.internal
```

## Configuration Examples

### Single Node (Development)

```yaml
instance_count: 1
product: dev
instance_flavor: small
```

Resources created: `dev-node-01`, `dev-vpc`, `dev-gateway`

### 3 Workers (Staging)

```yaml
instance_count: 3
product: staging
instance_flavor: medium
```

Resources created: `staging-node-01/02/03`, `staging-vpc`, `staging-gateway`

### 6 Workers (Production)

```yaml
instance_count: 6
product: prod
instance_flavor: large
instance_image: YOUR_SNAPSHOT_ID
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

- Change instance count: `pulumi config set instance_count 6`
- Add product name: `pulumi config set product prod`
- Use custom image: `pulumi config set instance_image YOUR_SNAPSHOT_ID`
- Add volumes: `pulumi config set extra_volumes '[{"suffix":"data","size":100}]'`
- Configure allowed IPs: `pulumi config set authorized_cidrs '["1.2.3.4/32"]'`
- Read full documentation: [README.md](../README.md)

## Common Issues

**Authentication fails:**
```bash
pulumi config set --secret scaleway:access_key YOUR_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET
```

**Wrong instance flavor:**
```bash
# Available flavors: tiny, small, medium, medium-plus, large, xlarge
pulumi config set instance_flavor medium
```

**Image not found:**
```bash
# Ensure instance_image is set to a valid snapshot ID
pulumi config set instance_image YOUR_SNAPSHOT_ID
```

## Production Checklist

Before deploying to production:

- [ ] Set `instance_count` appropriately
- [ ] Use production flavor (`medium` or higher)
- [ ] Set `product` for resource organization
- [ ] Use custom snapshot with your software (`instance_image`)
- [ ] **Configure `authorized_cidrs` to restrict gateway bastion access** (critical for production security)
- [ ] Configure additional volumes if needed (`extra_volumes`)
- [ ] Test in staging first
- [ ] Set up monitoring
- [ ] Document your configuration

## Get Help

- Full documentation: [README.md](../README.md)
- Configuration reference: [CONFIGURATION.md](CONFIGURATION.md)
- GitHub Action reference: [ACTION.md](ACTION.md)
- Pulumi docs: https://www.pulumi.com/docs/
- Scaleway docs: https://www.scaleway.com/en/docs/
