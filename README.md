# Multi-Cloud Platform Spawner

A production-grade, provider-agnostic infrastructure-as-code solution using Pulumi and Python to deploy configurable cluster topologies across multiple cloud providers.

## Overview

This project enables deployment of Rocky Linux clusters in three different topologies:

- **Single Node**: 1 worker node with gateway bastion for SSH access
- **3-Node Cluster**: 3 worker nodes with gateway bastion providing SSH access and NAT
- **6-Node Cluster**: 6 worker nodes with gateway bastion providing SSH access and NAT

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

#### Option A: Interactive Setup (Recommended)

Use the interactive setup script for easy configuration:

```bash
# Run the interactive setup script
./setup.sh

# The script will guide you through:
# - Creating or selecting a stack
# - Entering Scaleway credentials
# - Choosing topology and configuration
# - Setting up SSH keys (optional)
# - Configuring additional volumes (optional)
```

#### Option B: Manual Configuration

Configure manually with Pulumi CLI commands:

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
- 1 VPC and Private Network
- 1 Public Gateway with SSH bastion feature
- 1 Security Group (internal)
- 1 Rocky Linux worker node (private only)

### Deploy 3-Node Cluster

Secure cluster with gateway bastion for production use.

```bash
# Configure
pulumi config set topology 3-nodes

# Deploy
pulumi up

# Access gateway bastion
GATEWAY_IP=$(pulumi stack output gateway_bastion_ip)
ssh <username>@$GATEWAY_IP

# From gateway, access internal nodes via private network
# (Worker nodes are only accessible via gateway bastion)
```

**Resources Created:**
- 1 VPC
- 1 Private Network (192.168.10.0/24)
- 1 Public Gateway (SSH bastion + NAT + DHCP)
- 1 Security Group (internal)
- 3 Worker nodes (private only)

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
- 6 Worker nodes (private only): node-01 through node-06

### Image Configuration

The spawner uses images for worker nodes:

- **Worker Nodes**: Either uses your custom snapshot OR marketplace OS image

```bash
# Option 1: Use custom snapshot for workers (production)
pulumi config set worker_snapshot_id 11111111-2222-3333-4444-555555555555
pulumi up

# Option 2: Use marketplace image for workers (development/testing)
# Just don't set worker_snapshot_id - workers will use rockylinux 9
pulumi config rm worker_snapshot_id  # Remove if previously set
pulumi up

# Optional: Customize marketplace OS (defaults to Rocky Linux 9)
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
  "gateway_bastion_ip": "51.159.x.x",
  "nodes": {
    "node-01": {
      "id": "fr-par-1/...",
      "name": "node-01",
      "instance_type": "PRO2-S",
      "private_ip": "192.168.10.x",
      "ssh_command": "ssh -J bastion@51.159.x.x:61000 artesca-os@node-01.3-nodes-internal.internal"
    },
    "node-02": {
      "id": "fr-par-1/...",
      "name": "node-02",
      "instance_type": "PRO2-S",
      "private_ip": "192.168.10.x",
      "ssh_command": "ssh -J bastion@51.159.x.x:61000 artesca-os@node-02.3-nodes-internal.internal"
    },
    ...
  },
  "network": {
    "vpc_id": "...",
    "private_network_id": "...",
    "subnet": "192.168.10.0/24",
    "gateway_id": "..."
  },
  "config": {
    "topology": "single-node",
    "provider": "scaleway",
    "region": "fr-par",
    "zone": "fr-par-1",
    "ssh_access": "Gateway bastion (no bastion VM)",
    "worker_image": "11111111-2222-...",
    "instance_types": {
      "gateway_bastion": "VPC-GW-S",
      "worker_nodes": "PRO2-S"
    }
  }
}
```

**Key Points:**
- Gateway bastion IP is exported as `gateway_bastion_ip`
- Each node includes a ready-to-use `ssh_command` for easy SSH jump access
- SSH commands use port 61000 for the gateway bastion connection
- Each node output includes its `instance_type`
- Worker nodes show the configured instance type (default: `PRO2-S`)
- All nodes are private-only (no public IPs)
- SSH access is via the gateway bastion

### Connecting to Nodes

The easiest way to connect to your nodes is using the pre-generated SSH commands:

```bash
# Get the SSH command for a specific node
SSH_CMD=$(pulumi stack output --json | jq -r '.nodes."node-01".ssh_command')
echo $SSH_CMD

# Execute it directly
eval $SSH_CMD

# Or copy-paste from the output
pulumi stack output --json | jq -r '.nodes."node-01".ssh_command'
# Output: ssh -J bastion@51.159.x.x:61000 artesca-os@node-01.3-nodes-internal.internal

# Connect to different nodes
pulumi stack output --json | jq -r '.nodes."node-02".ssh_command'
pulumi stack output --json | jq -r '.nodes."node-03".ssh_command'
```

**Alternative methods:**

```bash
# Method 1: Manual SSH jump command
GATEWAY_IP=$(pulumi stack output gateway_bastion_ip)
ssh -J bastion@$GATEWAY_IP:61000 artesca-os@node-01.3-nodes-internal.internal

# Method 2: Two-hop SSH (first to gateway, then to node)
ssh artesca-os@$GATEWAY_IP
# Once on gateway:
ssh node-01.3-nodes-internal.internal
```

**SSH Command Format:**
```
ssh -J bastion@<gateway_ip>:61000 artesca-os@<node_name>.<network_name>.internal
```

Where:
- `<gateway_ip>`: Gateway bastion public IP
- `61000`: Gateway bastion SSH port
- `<node_name>`: Node name (e.g., node-01, node-02)
- `<network_name>`: Private network name (e.g., 3-nodes-internal)

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
| `bastion_os_name` | OS for workers (if no snapshot) | `rockylinux` |
| `bastion_os_version` | OS version for workers | `9` |
| `worker_snapshot_id` | Snapshot for workers (if not set, uses marketplace image) | `None` |
| `instance_type` | Instance size for worker nodes | `PRO2-S` |

**Note:** SSH access is provided via Scaleway's Public Gateway bastion feature (VPC-GW-S).

### Scaleway Instance Types

| Type | vCPUs | RAM | Use Case | Used For |
|------|-------|-----|----------|----------|
| `VPC-GW-S` | N/A | N/A | Gateway | **SSH bastion + NAT (always)** |
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

## Network Architecture (All Topologies)

```
Internet
   │
   │
   └─────────► Public Gateway (VPC-GW-S)
                  │ - SSH Bastion (Port 22)
                  │ - NAT for outbound
                  │ - DHCP for private network
                  ↓
               Private Network (192.168.10.0/24)
                  │
                  ├─► Node 01 (Private only, PRO2-S)
                  ├─► Node 02 (Private only, PRO2-S)
                  ├─► Node 03 (Private only, PRO2-S)
                  ├─► Node 04 (Private only, PRO2-S)
                  ├─► Node 05 (Private only, PRO2-S)
                  └─► Node 06 (Private only, PRO2-S)
```

**Topology Overview:**
- **single-node**: Gateway bastion + 1 worker node
- **3-nodes**: Gateway bastion + 3 worker nodes
- **6-nodes**: Gateway bastion + 6 worker nodes

**Security Model:**
- Gateway provides SSH bastion functionality (no separate bastion VM)
- SSH access to private nodes via gateway bastion
- Worker nodes are private-only, accessed via gateway
- Private nodes communicate via internal network
- Outbound internet access via gateway NAT
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
   
   # Note: Gateway always uses VPC-GW-S for SSH bastion + NAT
   ```

3. **Tag resources appropriately:**
   - Resources are auto-tagged with topology and management info
   - Use tags for cost allocation and resource tracking

### Security

1. **Never commit credentials:**
   - Pulumi config files with secrets are gitignored
   - Use `--secret` flag for sensitive values

2. **Limit gateway bastion access:**
   - Consider restricting SSH to specific IPs via firewall rules
   - Use SSH key authentication only
   - Configure gateway bastion security settings in Scaleway console

3. **Regular updates:**
   - Worker node images use marketplace or custom snapshots
   - Redeploy periodically to get security patches
   - Gateway is managed by Scaleway and auto-updated

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

