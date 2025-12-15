# Multi-Cloud Platform Spawner

A production-grade, provider-agnostic infrastructure-as-code solution using Pulumi and Python to deploy configurable cluster topologies across multiple cloud providers.

## Overview

This project enables deployment of Rocky Linux clusters in three different topologies:

- **Single Node**: Standalone instance for development or simple applications
- **3-Node Cluster**: Bootstrap + Bastion + 1 Slave node with private networking
- **6-Node Cluster**: Bootstrap + Bastion + 4 Slave nodes with private networking

The architecture is designed for multi-cloud support with clean abstractions, starting with Scaleway and designed for future AWS and OVH implementations.

## Architecture

```
┌─────────────────────────────────────────┐
│           User Configuration            │
│         (Pulumi Config Files)           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Core Abstractions Layer         │
│  (Provider-agnostic interfaces & models)│
│  - ClusterInterface                     │
│  - NetworkInterface                     │
│  - ComputeInterface                     │
│  - Topology Factory                     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│        Provider Implementations         │
│  ┌─────────────────────────────────┐   │
│  │  Scaleway (Implemented)         │   │
│  │  - ScalewayCluster              │   │
│  │  - ScalewayNetwork (VPC/Gateway)│   │
│  │  - ScalewayCompute (Instances)  │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  AWS (Planned)                  │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  OVH (Planned)                  │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Prerequisites

- **Python**: 3.8 or higher
- **uv**: Fast Python package installer ([Install uv](https://github.com/astral-sh/uv))
- **Pulumi CLI**: [Install Pulumi](https://www.pulumi.com/docs/get-started/install/)
- **Scaleway Account**: With API credentials
- **Git**: For version control

## Installation

### 1. Clone and Setup

```bash
# Navigate to the project directory
cd new-platform-spawner

# Install uv if not already installed
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or with pip: pip install uv

# Install dependencies with uv (fast!)
uv pip install -r requirements.txt

# Alternative: Use traditional venv if preferred
# python3 -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt
```

### 2. Configure Scaleway Credentials

Obtain your Scaleway API credentials from the [Scaleway Console](https://console.scaleway.com/):

1. Navigate to **IAM** → **API Keys**
2. Generate a new API key pair
3. Note down the **Access Key** and **Secret Key**
4. Get your **Project ID** from the project settings

### 3. Initialize Pulumi Stack

```bash
# Initialize a new stack (e.g., "dev")
pulumi stack init dev

# Configure required settings
pulumi config set project_id YOUR_SCALEWAY_PROJECT_ID
pulumi config set topology single-node  # or "3-nodes" or "6-nodes"
pulumi config set worker_snapshot_id YOUR_SNAPSHOT_ID  # Snapshot for worker nodes

# Configure Scaleway credentials (stored encrypted)
pulumi config set --secret scaleway:access_key YOUR_ACCESS_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET_KEY

# Optional: Override defaults
pulumi config set bastion_os_name rockylinux  # OS for bastion (default)
pulumi config set bastion_os_version 9  # OS version for bastion (default)
pulumi config set region fr-par
pulumi config set zone fr-par-1
pulumi config set instance_type PRO2-S  # Instance type for worker nodes
```

## Usage

### Deploy Single Node (Development)

Perfect for testing or single-application deployments.

```bash
# Configure
pulumi config set topology single-node

# Preview changes
pulumi preview

# Deploy
pulumi up

# Get outputs
pulumi stack output public_ip
```

**Resources Created:**
- 1 Security Group (SSH access)
- 1 Rocky Linux instance with public IP

### Deploy 3-Node Cluster

Secure cluster with bastion host pattern for production use.

```bash
# Configure
pulumi config set topology 3-nodes

# Deploy
pulumi up

# Access bastion
BASTION_IP=$(pulumi stack output bastion_public_ip)
ssh root@$BASTION_IP

# From bastion, access internal nodes via private network
# (Bootstrap and Slave nodes are only accessible via private network)
```

**Resources Created:**
- 1 VPC
- 1 Private Network (192.168.10.0/24)
- 1 Public Gateway (NAT + DHCP)
- 2 Security Groups (bastion and internal)
- 1 Bootstrap node (private only)
- 1 Bastion node (public + private)
- 1 Slave node (private only)

### Deploy 6-Node Cluster

Large cluster for distributed applications.

```bash
# Configure
pulumi config set topology 6-nodes

# Deploy
pulumi up

# View all outputs
pulumi stack output --json
```

**Resources Created:**
- Same network infrastructure as 3-node
- 1 Bootstrap node (private)
- 1 Bastion node (public + private)
- 4 Slave nodes (private): slave-01, slave-02, slave-03, slave-04

### Image Configuration

The spawner uses different images for different node types:

- **Bastion Node**: Uses marketplace OS image (always the latest patched version from Scaleway marketplace)
- **Worker Nodes**: Either uses your custom snapshot OR falls back to same OS as bastion

```bash
# Option 1: Use custom snapshot for workers (production)
pulumi config set worker_snapshot_id 11111111-2222-3333-4444-555555555555
pulumi up

# Option 2: Use same OS as bastion for workers (development/testing)
# Just don't set worker_snapshot_id - workers will use rockylinux 9
pulumi config rm worker_snapshot_id  # Remove if previously set
pulumi up

# Optional: Customize bastion OS (defaults to Rocky Linux 9)
pulumi config set bastion_os_name ubuntu
pulumi config set bastion_os_version jammy
```

**Use Cases for Worker Snapshots:**
- Pre-configured Artesca OS
- Pre-installed software stack
- Security-hardened base images
- Custom kernel configurations
- Company-specific base images

**Use Cases for Marketplace Images (no snapshot):**
- Development and testing
- Quick prototyping
- When you don't need custom software pre-installed

**Finding Your Snapshot ID:**
1. Go to [Scaleway Console → Images](https://console.scaleway.com/instance/images)
2. Find your snapshot or custom image (not volume snapshots!)
3. Copy the UUID
4. Set it with `pulumi config set worker_snapshot_id YOUR_UUID`

**Why Separate Images?**
- **Bastion**: Small, lightweight OS for SSH access only - always up-to-date from marketplace
- **Workers**: Custom snapshot with your application stack pre-installed, or marketplace image for testing

### Switching Topologies

You can change topologies by updating the configuration:

```bash
# Change from single-node to 3-nodes
pulumi config set topology 3-nodes

# Pulumi will destroy old resources and create new ones
pulumi up
```

**Note**: Changing topologies will destroy existing infrastructure. Always backup data before switching.

### Destroy Infrastructure

```bash
# Preview what will be destroyed
pulumi destroy --preview

# Destroy all resources
pulumi destroy
```

## Pulumi Outputs

After deployment, Pulumi exports useful information about your infrastructure. View outputs with:

```bash
# View all outputs
pulumi stack output --json

# View specific output
pulumi stack output bastion_public_ip
```

### Output Structure

**For all topologies:**

```json
{
  "topology": "single-node|3-nodes|6-nodes",
  "bastion_public_ip": "51.159.x.x",
  "nodes": {
    "bastion": {
      "id": "fr-par-1/...",
      "name": "bastion",
      "instance_type": "PLAY2-NANO",
      "public_ip": "51.159.x.x",
      "private_ip": "192.168.10.x"
    },
    "node-01": {
      "id": "fr-par-1/...",
      "name": "node-01",
      "instance_type": "PRO2-S",
      "private_ip": "192.168.10.x"
    },
    ...
  },
  "network": {
    "vpc_id": "...",
    "private_network_id": "...",
    "subnet": "192.168.10.0/24"
  },
  "config": {
    "topology": "single-node",
    "provider": "scaleway",
    "region": "fr-par",
    "zone": "fr-par-1",
    "bastion_os": "rockylinux 9",
    "worker_snapshot_id": "11111111-2222-...",
    "instance_types": {
      "bastion": "PLAY2-NANO",
      "worker_nodes": "PRO2-S"
    }
  }
}
```

**Key Points:**
- Each node output includes its `instance_type`
- Bastion always shows `PLAY2-NANO`
- Worker nodes show the configured instance type (default: `PRO2-S`)
- Only bastion has a `public_ip` field
- All nodes in multi-node topologies have `private_ip`

## Configuration Reference

### Required Configuration

| Key | Description | Example |
|-----|-------------|---------|
| `project_id` | Scaleway project ID | `12345678-1234-...` |
| `topology` | Cluster topology | `single-node`, `3-nodes`, or `6-nodes` |

### Optional Configuration

| Key | Description | Default |
|-----|-------------|---------|
| `provider` | Cloud provider | `scaleway` |
| `region` | Provider region | `fr-par` |
| `zone` | Provider zone | `fr-par-1` |
| `bastion_os_name` | OS for bastion node | `rockylinux` |
| `bastion_os_version` | OS version for bastion | `9` |
| `worker_snapshot_id` | Snapshot for workers (if not set, uses bastion OS) | `None` |
| `instance_type` | Instance size for worker nodes | `PRO2-S` |

**Note:** Bastion always uses `PLAY2-NANO` (small machine for SSH access only).

### Scaleway Instance Types

| Type | vCPUs | RAM | Use Case | Used For |
|------|-------|-----|----------|----------|
| `PLAY2-NANO` | 2 | 2 GB | Development | **Bastion (always)** |
| `PLAY2-MICRO` | 4 | 4 GB | Development | Worker nodes |
| `PRO2-S` | 4 | 8 GB | Production | **Worker nodes (default)** |
| `PRO2-M` | 8 | 16 GB | Production | Worker nodes |
| `PRO2-L` | 16 | 32 GB | Production | Worker nodes |

### Scaleway Regions and Zones

- **Paris** (`fr-par`): `fr-par-1`, `fr-par-2`, `fr-par-3`
- **Amsterdam** (`nl-ams`): `nl-ams-1`, `nl-ams-2`
- **Warsaw** (`pl-waw`): `pl-waw-1`, `pl-waw-2`

## Project Structure

```
new-platform-spawner/
├── __main__.py                    # Entry point
├── Pulumi.yaml                    # Project metadata
├── requirements.txt               # Python dependencies
├── README.md                      # This file
│
├── core/                          # Provider-agnostic abstractions
│   ├── interfaces.py              # Abstract base classes
│   ├── models.py                  # Data models
│   ├── topology.py                # Topology configurations
│   └── factory.py                 # Provider factory
│
├── providers/                     # Provider implementations
│   ├── scaleway/
│   │   ├── cluster.py             # Cluster orchestration
│   │   ├── network.py             # VPC, Private Network, Gateway
│   │   ├── compute.py             # Instances, Security Groups
│   │   ├── images.py              # OS image lookup
│   │   └── config.py              # Scaleway-specific config
│   ├── aws/                       # Future AWS implementation
│   └── ovh/                       # Future OVH implementation
│
└── config/                        # Configuration defaults
    └── defaults.py
```

## Network Architecture (Multi-Node Topologies)

```
Internet
   │
   ├─────────► Bastion Node (Public IP, PLAY2-NANO)
   │              ↓ (SSH Access)
   │           Private Network (192.168.10.0/24)
   │              │
   │              ├─► Node 01 (Private only, PRO2-S)
   │              ├─► Node 02 (Private only, PRO2-S)
   │              ├─► Node 03 (Private only, PRO2-S)
   │              ├─► Node 04 (Private only, PRO2-S)
   │              ├─► Node 05 (Private only, PRO2-S)
   │              └─► Node 06 (Private only, PRO2-S)
   │
   └─────────► Public Gateway (NAT)
                  ↑ (Outbound Internet)
                  └─ All private nodes
```

**Topology Overview:**
- **single-node**: 1 bastion (PLAY2-NANO) + 1 worker node
- **3-nodes**: 1 bastion (PLAY2-NANO) + 3 worker nodes
- **6-nodes**: 1 bastion (PLAY2-NANO) + 6 worker nodes

**Security Model:**
- Only bastion has inbound SSH access from internet
- Bastion is always a small machine (PLAY2-NANO) for SSH access only
- Worker nodes are private-only, accessed via bastion
- Private nodes communicate via internal network
- Outbound internet access via NAT gateway
- Security groups enforce network isolation

## Extending the Platform

### Adding a New Provider (e.g., AWS)

1. **Create provider directory:**
   ```bash
   mkdir -p providers/aws
   ```

2. **Implement the interfaces:**
   ```python
   # providers/aws/cluster.py
   from core.interfaces import ClusterInterface
   
   class AWSCluster(ClusterInterface):
       def deploy_single_node(self):
           # AWS-specific implementation
           pass
       
       def deploy_three_node(self):
           # AWS-specific implementation
           pass
       
       def deploy_six_node(self):
           # AWS-specific implementation
           pass
   ```

3. **Implement network and compute:**
   - `providers/aws/network.py`: VPC, Subnets, NAT Gateway
   - `providers/aws/compute.py`: EC2 instances, Security Groups

4. **Update factory:**
   ```python
   # core/factory.py
   if config.provider == Provider.AWS:
       from providers.aws.cluster import AWSCluster
       return AWSCluster(config)
   ```

5. **Add dependencies:**
   ```bash
   # requirements.txt
   pulumi-aws>=6.0.0
   ```

### Adding a New Topology

1. **Update the Topology enum:**
   ```python
   # core/models.py
   class Topology(Enum):
       NINE_NODE = "9-nodes"
   ```

2. **Create topology configuration:**
   ```python
   # core/topology.py
   def _get_nine_node_config(instance_type: str):
       # Define nodes...
       return {"nodes": nodes, "network": network_config}
   ```

3. **Implement deployment method:**
   ```python
   # providers/scaleway/cluster.py
   def deploy_nine_node(self):
       # Implementation...
       pass
   ```

## Troubleshooting

### Pulumi State Issues

```bash
# Refresh state from cloud provider
pulumi refresh

# Export state for backup
pulumi stack export > stack-backup.json

# Import state
pulumi stack import < stack-backup.json
```

### Image Not Found

If bastion OS image lookup fails:

```bash
# Verify image label exists in your zone
pulumi config set bastion_os_name rockylinux
pulumi config set bastion_os_version 9
```

If worker snapshot not found:

```bash
# Verify your snapshot ID is correct and in the same zone
pulumi config set worker_snapshot_id YOUR_SNAPSHOT_ID
```

### Authentication Errors

```bash
# Verify credentials are set
pulumi config get scaleway:access_key
pulumi config get scaleway:secret_key

# Re-set if needed
pulumi config set --secret scaleway:access_key YOUR_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET
```

### Network Connectivity Issues

For multi-node deployments, if private nodes can't reach internet:

1. Verify gateway is created: `pulumi stack output network`
2. Check security groups allow outbound traffic
3. Verify DHCP is enabled on gateway network
4. Check instance network interfaces are attached

## Best Practices

### Development Workflow

1. **Use separate stacks for environments:**
   ```bash
   pulumi stack init dev
   pulumi stack init staging
   pulumi stack init prod
   ```

2. **Use different worker node instance types per environment:**
   ```bash
   # Development: smaller worker nodes
   pulumi config set instance_type PLAY2-MICRO --stack dev
   
   # Production: larger worker nodes
   pulumi config set instance_type PRO2-M --stack prod
   
   # Note: Bastion always uses PLAY2-NANO regardless of this setting
   ```

3. **Tag resources appropriately:**
   - Resources are auto-tagged with topology and management info
   - Use tags for cost allocation and resource tracking

### Security

1. **Never commit credentials:**
   - Pulumi config files with secrets are gitignored
   - Use `--secret` flag for sensitive values

2. **Limit bastion access:**
   - Consider restricting SSH to specific IPs
   - Use SSH key authentication only
   - Implement fail2ban or similar

3. **Regular updates:**
   - Rocky Linux images are dynamically looked up
   - Redeploy periodically to get security patches

### Production Deployment

1. **Use production instance types for worker nodes:**
   ```bash
   # PRO2-S is the default (recommended for most workloads)
   pulumi config set instance_type PRO2-S
   
   # Or use larger instances for heavy workloads
   pulumi config set instance_type PRO2-M
   ```

2. **Enable monitoring:**
   - Use Scaleway's monitoring features
   - Set up alerts for resource usage

3. **Implement backups:**
   - Attach block volumes for persistent data
   - Regular snapshots of volumes
   - Export Pulumi state regularly

4. **Infrastructure as Code best practices:**
   - Version control all code changes
   - Use pull requests for reviews
   - Test in dev/staging before production

## Advanced Usage

### Custom Cloud-Init Scripts

Add user data to nodes for automated configuration:

```python
# In __main__.py or by modifying topology.py
node_config.user_data = """#!/bin/bash
yum update -y
yum install -y docker
systemctl enable docker
systemctl start docker
"""
```

### Adding Block Storage

Modify the cluster implementation to add persistent storage:

```python
# providers/scaleway/cluster.py
volume = scaleway.instance.Volume(
    "data-volume",
    size_in_gb=100,
    type="b_ssd",
    zone=self.config.zone
)

# Attach to bootstrap node
instance_output = self.compute.create_instance(
    # ...
    additional_volume_ids=[volume.id]
)
```

### Multiple Regions

Deploy across multiple regions by creating multiple stacks:

```bash
# Paris stack
pulumi stack init paris
pulumi config set region fr-par --stack paris
pulumi up --stack paris

# Amsterdam stack  
pulumi stack init amsterdam
pulumi config set region nl-ams --stack amsterdam
pulumi up --stack amsterdam
```

## Contributing

Contributions are welcome! Areas for contribution:

1. **New Providers**: AWS, OVH, GCP, Azure implementations
2. **New Topologies**: Custom cluster configurations
3. **Features**: Load balancers, auto-scaling, monitoring
4. **Documentation**: Tutorials, architecture diagrams
5. **Testing**: Unit tests, integration tests

## License

[Your License Here]

## Additional Documentation

- **[CUSTOM_IMAGES.md](CUSTOM_IMAGES.md)**: Complete guide to using custom images and snapshots
- **[QUICKSTART.md](QUICKSTART.md)**: 5-minute quick start guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Technical architecture deep dive
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)**: Implementation details and metrics

## Support

For issues and questions:

- **GitHub Issues**: [Project Issues]
- **Documentation**: [Pulumi Documentation](https://www.pulumi.com/docs/)
- **Scaleway Docs**: [Scaleway Documentation](https://www.scaleway.com/en/docs/)

## Acknowledgments

Based on research into migrating from OVH to Scaleway using Pulumi with Python, emphasizing infrastructure-as-code best practices and multi-cloud architecture patterns.

