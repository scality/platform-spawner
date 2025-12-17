# Platform Spawner - Live Demonstration

**Multi-Cloud Infrastructure-as-Code using Pulumi + Python**

---

## 🎯 What We Built

A production-grade, provider-agnostic infrastructure solution that deploys configurable Rocky Linux cluster topologies across cloud providers.

### Key Features

✅ **Multiple Topologies**
- Single Node (1 worker)
- 3-Node Cluster (3 workers)
- 6-Node Cluster (6 workers)

✅ **Multi-Cloud Ready Architecture**
- Clean abstractions (ClusterInterface, NetworkInterface, ComputeInterface)
- Scaleway fully implemented
- AWS provider is not done yet

✅ **Secure by Design**
- Private-only worker nodes
- Gateway bastion for SSH access (port 61000)
- Pre-generated SSH jump commands for each node
- Security groups and network isolation
- NAT for outbound internet

✅ **Flexible Image Management**
- Custom snapshots (pre-configured OS)
- Marketplace images (vanilla OS)
- Perfect for both dev and production

---

## 🏗️ Architecture Overview

```
                    Internet
                       │
                       │
                       ▼
            ┌─────────────────────┐
            │  Public Gateway      │
            │  (VPC-GW-S)         │
            │  - SSH Bastion      │
            │  - NAT              │
            │  - DHCP             │
            └──────────┬──────────┘
                       │
            Private Network (192.168.10.0/24)
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    Node-01        Node-02       Node-03
    (PRO2-S)       (PRO2-S)      (PRO2-S)
    Private IP     Private IP    Private IP
```

### Security Model
- ✅ **Gateway bastion**: Single SSH entry point
- ✅ **Private-only nodes**: No direct internet exposure
- ✅ **NAT**: Outbound internet via gateway
- ✅ **Internal communication**: Via private network

---

## 🔑 SSH Access Made Easy

**Every node includes a ready-to-use SSH command!**

No need to manually construct complex SSH jump commands - each node output includes a pre-generated `ssh_command`:

```bash
# Simply copy-paste the SSH command from outputs
pulumi stack output --json | jq -r '.nodes."node-01".ssh_command'

# Output example:
ssh -J bastion@51.159.x.x:61000 artesca-os@node-01.3-nodes-internal.internal
```

**Format:** `ssh -J bastion@<gateway_ip>:61000 artesca-os@<node>.<network>.internal`

---

## 📋 Prerequisites

Quick setup requirements:

```bash
✓ Python 3.8+
✓ Pulumi CLI installed
✓ Scaleway API credentials
✓ uv package manager (optional, but 10x faster)
```

---

## ⚙️ Configuration

### Option 1: Interactive Setup Script (Recommended)

The easiest way to configure your stack:

```bash
# Run the interactive setup script
./setup.sh

# The script will:
# ✓ Create or select a stack
# ✓ Prompt for all required settings
# ✓ Provide helpful defaults
# ✓ Validate inputs
# ✓ Apply configuration
# ✓ Optionally preview/deploy
```

### Option 2: Manual Configuration

```bash
# Initialize stack
pulumi stack init demo

# Minimum required configuration
pulumi config set project_id YOUR_SCALEWAY_PROJECT_ID
pulumi config set topology single-node

# Scaleway credentials (encrypted)
pulumi config set --secret scaleway:access_key YOUR_ACCESS_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET_KEY
```

### Optional Settings

```bash
# Region & Zone (default: fr-par / fr-par-1)
pulumi config set region fr-par
pulumi config set zone fr-par-1

# Instance type for workers (default: PRO2-S)
pulumi config set instance_type PRO2-S

# Custom snapshot for workers (if not set, uses marketplace image)
pulumi config set worker_snapshot_id YOUR_SNAPSHOT_UUID

# OS for marketplace image (if no snapshot)
pulumi config set bastion_os_name rockylinux
pulumi config set bastion_os_version 9
```

### Configuration Matrix

| Setting | Options | Use Case |
|---------|---------|----------|
| **topology** | `single-node`, `3-nodes`, `6-nodes` | Cluster size |
| **instance_type** | `PLAY2-MICRO`, `PRO2-S`, `PRO2-M`, `PRO2-L` | Worker node sizing |
| **worker_snapshot_id** | UUID or empty | Custom vs marketplace image |
| **region** | `fr-par`, `nl-ams`, `pl-waw` | Scaleway region |

---

## 🚀 Deployment Demo

### Step 1: Install Dependencies

```bash
# Fast installation with uv
uv pip install -r requirements.txt

# Traditional method (slower)
pip install -r requirements.txt
```

**Requirements:**
- `pulumi>=3.0.0`
- `pulumiverse-scaleway>=1.0.0`
- `pyyaml>=6.0`

### Step 1.5: Run Interactive Setup

```bash
# Run the setup script (recommended for first-time setup)
./setup.sh
```

**What the script does:**
- ✓ Creates or selects a Pulumi stack
- ✓ Prompts for Scaleway credentials
- ✓ Guides through topology selection
- ✓ Configures region, zone, instance types
- ✓ Optionally sets up SSH keys
- ✓ Can preview and deploy immediately

**Skip to Step 5 if using setup.sh!**

---

**Alternative: Manual Configuration**

If you prefer manual configuration, continue with Step 2:

### Step 2: Single Node Deployment

Perfect for development or testing:

```bash
# Configure
pulumi config set topology single-node

# Preview infrastructure
pulumi preview

# Deploy
pulumi up -y

# Get gateway IP for SSH access
pulumi stack output gateway_bastion_ip
```

**What gets created:**
- 1 VPC
- 1 Private Network
- 1 Public Gateway (VPC-GW-S) with SSH bastion
- 1 Security Group
- 1 Worker node (PRO2-S, private-only)

### Step 3: Scale to 3-Node Cluster

Production-ready cluster:

```bash
# Update topology
pulumi config set topology 3-nodes

# Deploy changes
pulumi up
```

**What gets created:**
- Same network infrastructure
- **3 worker nodes** instead of 1
- All nodes on private network (192.168.10.0/24)

### Step 4: View Infrastructure

```bash
# Get all outputs
pulumi stack output --json

# Example output:
{
  "topology": "3-nodes",
  "gateway_bastion_ip": "51.159.x.x",
  "nodes": {
    "node-01": {
      "name": "node-01",
      "instance_type": "PRO2-S",
      "private_ip": "192.168.10.x",
      "ssh_command": "ssh -J bastion@51.159.x.x:61000 artesca-os@node-01.3-nodes-internal.internal"
    },
    "node-02": {
      "name": "node-02",
      "instance_type": "PRO2-S",
      "private_ip": "192.168.10.x",
      "ssh_command": "ssh -J bastion@51.159.x.x:61000 artesca-os@node-02.3-nodes-internal.internal"
    },
    "node-03": { ... }
  },
  "network": {
    "vpc_id": "...",
    "subnet": "192.168.10.0/24"
  }
}
```

### Step 5: Access Infrastructure

```bash
# Get the gateway bastion IP
GATEWAY_IP=$(pulumi stack output gateway_bastion_ip)
echo $GATEWAY_IP

# Option 1: Use the pre-generated SSH command from outputs
pulumi stack output --json | jq -r '.nodes."node-01".ssh_command'
# Example output: ssh -J bastion@51.159.x.x:61000 artesca-os@node-01.3-nodes-internal.internal

# Option 2: Manually construct the SSH jump command
ssh -J bastion@$GATEWAY_IP:61000 artesca-os@node-01.3-nodes-internal.internal
ssh -J bastion@$GATEWAY_IP:61000 artesca-os@node-02.3-nodes-internal.internal
ssh -J bastion@$GATEWAY_IP:61000 artesca-os@node-03.3-nodes-internal.internal

# Option 3: First SSH to gateway, then to nodes
ssh artesca-os@$GATEWAY_IP
# Then from gateway:
ssh node-01.3-nodes-internal.internal
```

### Step 6: Cleanup

```bash
# Preview deletion
pulumi destroy --preview

# Destroy all resources
pulumi destroy
```

---

## 🎨 Image Management

### Option 1: Custom Snapshot (Production)

Pre-configured, ready-to-go images:

```bash
pulumi config set worker_snapshot_id 11111111-2222-3333-4444-555555555555
pulumi up
```

**Use cases:**
- ✅ Artesca OS pre-installed
- ✅ Security-hardened base
- ✅ Custom software stack
- ✅ Faster deployment

### Option 2: Marketplace Image (Development)

Fresh OS from marketplace:

```bash
# Don't set worker_snapshot_id
pulumi config rm worker_snapshot_id
pulumi up
```

**Use cases:**
- ✅ Development & testing
- ✅ Quick prototyping
- ✅ Vanilla OS needed

---

## 📊 Infrastructure-as-Code Benefits

### What We Achieved

✅ **Version Control**
- Infrastructure changes tracked in Git
- Code reviews for infrastructure
- Rollback capability

✅ **Repeatability**
- Same config = same infrastructure
- No manual steps
- No configuration drift

✅ **Multi-Environment**
```bash
pulumi stack init dev
pulumi stack init staging
pulumi stack init prod
```

✅ **Cost Management**
- Destroy dev environments when not in use
- Predictable infrastructure costs
- Easy to scale up/down

---

## 🔄 Multi-Cloud Architecture

### Clean Abstractions

```python
# Core interfaces (provider-agnostic)
ClusterInterface
  ├── deploy()
  ├── destroy()
  
NetworkInterface
  ├── create_vpc()
  ├── create_private_network()
  
ComputeInterface
  ├── create_instance()
  ├── create_security_group()
```

### Current Status

| Provider | Status | Features |
|----------|--------|----------|
| **Scaleway** | ✅ Implemented | VPC, Gateway, Instances, Snapshots |
| **AWS** | 📋 Planned | VPC, EC2, NAT Gateway |
| **OVH** | 📋 Planned | vRack, Instances, Networking |

### Adding New Provider

Just implement the interfaces:

```python
# providers/aws/cluster.py
class AWSCluster(ClusterInterface):
    def deploy(self):
        # AWS-specific implementation
        pass
```

---

## 🎯 Key Differentiators

### Why This Solution?

1. **Provider-Agnostic Design**
   - Not locked into Scaleway
   - Easy to add new providers
   - Reusable abstractions

2. **Python + Pulumi**
   - Real programming language (not DSL)
   - Type safety and IDE support
   - Unit testable

3. **Production-Ready**
   - Security best practices
   - Network isolation
   - Monitoring-ready

4. **Developer-Friendly**
   - Clear documentation
   - Simple configuration
   - Fast deployment (< 5 minutes)

---

## 📈 Demo Scenarios

### Scenario 0: First-Time Setup (Easiest)

```bash
# Run the interactive setup - perfect for demos!
./setup.sh

# The script handles everything:
# - Stack creation
# - Credential setup
# - Topology selection
# - Configuration validation
# - Optional immediate deployment

# Total time: ~2 minutes including deployment
```

### Scenario 1: Development Environment

```bash
# Small, cheap cluster for testing
pulumi config set topology single-node
pulumi config set instance_type PLAY2-MICRO
pulumi up
# ✅ 1 node deployed in ~3 minutes
```

### Scenario 2: Production Artesca Cluster

```bash
# Production-ready with custom image
pulumi config set topology 6-nodes
pulumi config set instance_type PRO2-S
pulumi config set worker_snapshot_id YOUR_ARTESCA_SNAPSHOT
pulumi up
# ✅ 6 nodes with Artesca OS in ~5 minutes
```

### Scenario 3: Multi-Region Deployment

```bash
# Paris cluster
pulumi stack init paris
pulumi config set region fr-par
pulumi up --stack paris

# Amsterdam cluster
pulumi stack init amsterdam
pulumi config set region nl-ams
pulumi up --stack amsterdam
```

---

## 🎤 Talking Points for Presentation

### Problem Statement
- Manual infrastructure = slow, error-prone
- Configuration drift between environments
- Hard to replicate setups
- Provider lock-in risk

### Our Solution
- Infrastructure-as-Code with Pulumi
- Provider-agnostic architecture
- Automated, repeatable deployments
- Version controlled infrastructure

### Results
- ✅ Deploy clusters in < 5 minutes
- ✅ Same config across environments
- ✅ Easy to add new providers
- ✅ Security built-in by design

### Next Steps
- Add AWS/OVH providers
- Implement auto-scaling
- Add monitoring integration
- CI/CD pipeline integration

---

## 📝 Quick Reference Card

### Most Common Commands

```bash
# Deploy
pulumi preview              # Dry-run
pulumi up                   # Deploy changes
pulumi destroy              # Tear down

# Configuration
pulumi config set KEY VALUE         # Set config
pulumi config set --secret KEY VAL  # Set secret
pulumi config                       # List all config

# Outputs
pulumi stack output                 # Show all outputs
pulumi stack output KEY             # Show specific output
pulumi stack output --json          # JSON format

# Stacks
pulumi stack ls                     # List stacks
pulumi stack select STACK           # Switch stack
pulumi stack init STACK             # Create stack
```

### Resource Types

| Resource | Purpose | Count |
|----------|---------|-------|
| VPC | Network isolation | 1 |
| Private Network | Internal communication | 1 |
| Public Gateway | SSH bastion + NAT | 1 |
| Security Group | Firewall rules | 1 |
| Worker Instances | Application nodes | 1, 3, or 6 |

### SSH Access Quick Reference

```bash
# Get SSH command for a specific node
pulumi stack output --json | jq -r '.nodes."node-01".ssh_command'

# Connect to a node using the pre-generated command
eval $(pulumi stack output --json | jq -r '.nodes."node-01".ssh_command')

# List all SSH commands for all nodes
pulumi stack output --json | jq -r '.nodes[].ssh_command'

# Save SSH commands to a file for reference
pulumi stack output --json | jq -r '.nodes[] | "\(.name): \(.ssh_command)"' > ssh-commands.txt
```

---

## 🙏 Conclusion

**Multi-Cloud Platform Spawner** demonstrates:

- ✅ Modern infrastructure practices
- ✅ Clean, maintainable code
- ✅ Production-ready architecture
- ✅ Future-proof design

**Thank you!**

Questions?

