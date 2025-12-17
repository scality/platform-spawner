# Quick Start Guide

Get up and running with the Multi-Cloud Platform Spawner in 5 minutes.

## Prerequisites

- Python 3.8+
- uv package manager ([Install](https://github.com/astral-sh/uv))
- Pulumi CLI installed
- Scaleway account with API credentials

## Step-by-Step Setup

### 1. Install Dependencies

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install packages with uv (blazingly fast!)
uv pip install -r requirements.txt
```

### 2. Get Scaleway Credentials

Visit [Scaleway Console](https://console.scaleway.com/):

1. Go to **IAM** → **API Keys** → **Generate new API Key**
2. Copy the **Access Key** and **Secret Key**
3. Get your **Project ID** from project settings

### 3. Initialize and Configure

**Easy way - Interactive setup:**

```bash
# Run the setup script
./setup.sh

# Follow the prompts to configure your stack
```

**Manual way - CLI commands:**

```bash
# Initialize Pulumi stack
pulumi stack init dev

# Set required config
pulumi config set project_id YOUR_PROJECT_ID
pulumi config set topology single-node

# Optional: Set worker snapshot (if not set, uses marketplace image)
# pulumi config set worker_snapshot_id YOUR_SNAPSHOT_ID

# Set secrets
pulumi config set --secret scaleway:access_key YOUR_ACCESS_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET_KEY
```

### 4. Deploy!

```bash
# Preview
pulumi preview

# Deploy
pulumi up

# Get the gateway bastion IP
pulumi stack output gateway_bastion_ip
```

### 5. Access Your Instances

```bash
# SSH via gateway bastion to access private instances
GATEWAY_IP=$(pulumi stack output gateway_bastion_ip)
ssh <username>@$GATEWAY_IP
```

## Try Different Topologies

### 3-Node Cluster

```bash
pulumi config set topology 3-nodes
pulumi up
```

### 6-Node Cluster

```bash
pulumi config set topology 6-nodes
pulumi up
```

## Image Configuration

The spawner uses images for worker nodes:

- **Worker Nodes**: Uses custom snapshot if provided, otherwise marketplace OS image

```bash
# Option 1: Use custom snapshot for workers (production)
pulumi config set worker_snapshot_id 11111111-2222-3333-4444-555555555555

# Option 2: Use marketplace image (development/testing)
# Simply don't set worker_snapshot_id

# Optional: Customize marketplace OS (defaults to Rocky Linux 9)
pulumi config set bastion_os_name rockylinux
pulumi config set bastion_os_version 9
```

## View Deployed Resources

After deployment, view information about your infrastructure:

```bash
# Get gateway bastion IP for SSH access
pulumi stack output gateway_bastion_ip

# View all outputs (includes instance types for each node)
pulumi stack output --json

# Example output shows:
# - gateway_bastion_ip: Public IP for SSH access
# - node-01, node-02, etc.: Worker nodes with private IPs
# - instance_types: VPC-GW-S (gateway), PRO2-S (workers)
```

## Clean Up

```bash
pulumi destroy
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore [core/topology.py](core/topology.py) to understand node configurations
- Check [providers/scaleway/](providers/scaleway/) for implementation details
- See the [research document](Pulumi-scaleway.md) for architectural background

## Common Issues

**"Image not found" error for workers:**
```bash
pulumi config set bastion_os_name rockylinux
pulumi config set bastion_os_version 9
```

**"worker snapshot not found" error:**
```bash
# Either use a valid snapshot/image ID
pulumi config set worker_snapshot_id YOUR_VALID_IMAGE_ID

# Or remove it to use marketplace image
pulumi config rm worker_snapshot_id
```

**Authentication fails:**
```bash
# Verify credentials are set
pulumi config get scaleway:access_key
# Re-set if empty
```

**Want to use different instance size for worker nodes:**
```bash
# PRO2-S is the default (recommended for production)
pulumi config set instance_type PRO2-S

# Note: Gateway bastion always uses VPC-GW-S (provides SSH + NAT)
```

## Configuration Quick Reference

| What | Command |
|------|---------|
| Change topology | `pulumi config set topology 3-nodes` |
| Change region | `pulumi config set region nl-ams` |
| Change zone | `pulumi config set zone nl-ams-1` |
| Set worker snapshot | `pulumi config set worker_snapshot_id YOUR_SNAPSHOT_ID` |
| Change worker node instance type | `pulumi config set instance_type PRO2-S` |
| Change worker OS (no snapshot) | `pulumi config set bastion_os_name rockylinux` |
| View all config | `pulumi config` |
| View all outputs | `pulumi stack output --json` |

## Production Checklist

Before deploying to production:

- [ ] Use production instance types for worker nodes (`PRO2-S` or higher)
- [ ] Gateway bastion automatically uses `VPC-GW-S` (managed by Scaleway)
- [ ] Use a dedicated stack (`pulumi stack init prod`)
- [ ] Review security group rules
- [ ] Set up monitoring and alerts
- [ ] Configure backup strategy
- [ ] Document your specific configuration
- [ ] Test disaster recovery procedure

## Help

- Full documentation: [README.md](README.md)
- Pulumi docs: https://www.pulumi.com/docs/
- Scaleway docs: https://www.scaleway.com/en/docs/

