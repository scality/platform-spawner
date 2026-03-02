# Multi-Cloud Platform Spawner

A production-grade infrastructure-as-code solution using Pulumi and Python to deploy configurable clusters with any number of worker nodes across cloud providers.

## Overview

This project deploys clusters with flexible configuration, including but not limited to Rocky Linux:

- **Any number of worker nodes**: 1, 3, 6, 12, 50, or any positive integer
- **Resource naming prefixes**: Organize resources with custom prefixes (dev, staging, prod, etc.)
- **Private network architecture**: All workers on private network with gateway bastion for SSH access
- **Custom or marketplace images**: Use pre-configured snapshots or fresh marketplace images (with automatic name resolution, e.g., `rocky-8` → `rockylinux_8`)
- **Additional volumes**: Attach multiple volumes per worker node with flexible sizing
- **Extra private networks**: Attach multiple network interfaces for multi-homed instances
- **Placement group**: All instances are co-located with enforced low-latency policy

The architecture is designed for multi-cloud support with clean abstractions, starting with Scaleway.

## Documentation

| Document | Description |
|----------|-------------|
| **[Quick Start Guide](docs/QUICKSTART.md)** | Deploy your first cluster in 5 minutes |
| **[Configuration Reference](docs/CONFIGURATION.md)** | All configurable fields, types, defaults, flavors, and examples |
| **[GitHub Action Reference](docs/ACTION.md)** | Action inputs, outputs, workflow examples, and troubleshooting |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Import a CI stack from S3 and re-run locally |

---

## Quick Start

### CLI Usage

```bash
# Install dependencies
uv pip install -r requirements.txt

# Configure
pulumi stack init dev
pulumi config set project_id YOUR_SCALEWAY_PROJECT_ID
pulumi config set instance_count 3
pulumi config set instance_image YOUR_SNAPSHOT_ID
pulumi config set product dev
pulumi config set --secret scaleway:access_key YOUR_ACCESS_KEY
pulumi config set --secret scaleway:secret_key YOUR_SECRET_KEY

# Deploy
pulumi up

# Access nodes
pulumi stack output nodes --json | jq -r '.[] | .ssh_command'

# Cleanup
pulumi destroy
```

### GitHub Action Usage

```yaml
- uses: scality/platform-spawner@v2
  with:
    action: spawn
    stack_name: my-cluster-${{ github.run_number }}
    product: my-app
    configuration: |
      instance_image: ${{ vars.SNAPSHOT_ID }}
      instance_count: 3
      instance_flavor: medium
    ssh_public_keys: '["ssh-ed25519 AAAA... user@host"]'
    scaleway_access_key: ${{ secrets.SCW_ACCESS_KEY }}
    scaleway_secret_key: ${{ secrets.SCW_SECRET_KEY }}
    scaleway_project_id: ${{ secrets.SCW_PROJECT_ID }}
```

See [GitHub Action Reference](docs/ACTION.md) for complete examples.

---

## Architecture

```mermaid
graph TD
    Internet([Internet])
    Gateway[Public Gateway<br/>- SSH Bastion<br/>- NAT for outbound<br/>- DHCP]
    PrivateNet[Private Network<br/>192.168.10.0/24]
    ExtraNet[Extra Network<br/>10.1.0.0/24<br/>optional]
    Node1[node-01<br/>PRO2-S]
    Node2[node-02<br/>PRO2-S]
    Node3[node-03<br/>PRO2-S]
    NodeN[node-N<br/>PRO2-S]

    Internet --> Gateway
    Gateway --> PrivateNet
    PrivateNet --> Node1
    PrivateNet --> Node2
    PrivateNet --> Node3
    PrivateNet --> NodeN
    ExtraNet -.-> Node1
    ExtraNet -.-> Node2
    ExtraNet -.-> Node3
    ExtraNet -.-> NodeN
```

### Security Model

- **Gateway bastion**: Single SSH entry point (port 61000)
- **IP-based access control**: Restrict gateway bastion access to specific IPs via `authorized_cidrs`
- **Private-only workers**: No direct internet exposure
- **NAT**: Outbound internet access via gateway
- **Security groups**: Network isolation and firewall rules
- **Placement group**: All instances are co-located in an enforced low-latency placement group for optimal network performance

---

## Key Features

### Instance Flavors

| Flavor | Scaleway Type | Use Case |
|--------|---------------|----------|
| `tiny` | `PLAY2-PICO` | Minimal testing |
| `small` | `PLAY2-NANO` | Light workloads |
| `medium` | `PRO2-S` | Development, small production |
| `large` | `PRO2-L` | High-performance |

See [Configuration Reference](docs/CONFIGURATION.md#flavor-reference) for the complete list.

### Extra Volumes

Attach additional block storage to each worker:

```yaml
extra_volumes:
  - suffix: data
    size: 500
    count: 4
```

### Extra Private Networks

Create multi-homed instances with isolated networks:

```yaml
extra_private_networks:
  - suffix: storage
    subnet: "10.1.0.0/24"
```

See [Configuration Reference](docs/CONFIGURATION.md#extra-resources) for details.

### Instance Image Resolution

The spawner intelligently resolves image references:

- **Marketplace labels**: e.g., `rockylinux_9` — used directly
- **User-friendly aliases**: e.g., `rocky-9` → mapped to `rockylinux_9`
- **Snapshot UUIDs**: boot volume created from snapshot
- **Dynamic lookup**: `images.py` resolves the latest image UUID for Rocky Linux, Ubuntu, and Debian

The bastion always uses the marketplace label format. See [Configuration Reference](docs/CONFIGURATION.md#image-resolution) for full details.

### Placement Group

All instances in a deployment share an **enforced low-latency placement group**. This ensures Scaleway co-locates them on the same hypervisor cluster for minimal network latency. The placement group is created automatically — no configuration needed.

> **Note**: If Scaleway cannot satisfy the low-latency constraint (capacity limits), the deployment will fail. Try a different availability zone or reduce `instance_count`.

---

## Output Structure

After deployment:

```bash
# View all outputs
pulumi stack output --json

# Get gateway IP
pulumi stack output gateway_bastion_ip

# Get SSH commands
pulumi stack output nodes --json | jq -r '.[] | .ssh_command'
```

### SSH Access

```bash
ssh -J bastion@<gateway_ip>:61000 artesca-os@<node_name>.<network_name>.internal
```

---

## Project Structure

```
platform-spawner/
├── __main__.py              # Entry point
├── action.yaml              # GitHub Action definition
├── Pulumi.yaml              # Project metadata
│
├── docs/                    # Documentation
│   ├── CONFIGURATION.md     # Configuration reference
│   └── ACTION.md            # GitHub Action reference
│
├── config/                  # Configuration utilities
│   ├── defaults.py          # Default values
│   └── flavors.py           # Flavor mappings
│
├── core/                    # Provider-agnostic abstractions
│   ├── interfaces.py        # Abstract base classes
│   ├── models.py            # Data models
│   ├── topology.py          # Node configurations
│   ├── ssh.py               # SSH key management
│   └── factory.py           # Provider factory
│
└── providers/               # Provider implementations
    └── scaleway/
        ├── cluster.py       # Cluster orchestration
        ├── network.py       # VPC, Gateway, Private Network
        ├── compute.py       # Instances, Security Groups
        ├── images.py        # OS image lookup
        └── config.py        # Scaleway configuration
```

---

## Contributing

The project uses clean abstractions to support multiple cloud providers:

```python
# Add new provider by implementing interfaces
class AWSCluster(ClusterInterface):
    def deploy_cluster(self):
        # AWS-specific implementation
        pass
```

---

## Support

- [Configuration Reference](docs/CONFIGURATION.md)
- [GitHub Action Reference](docs/ACTION.md)
- [Pulumi Documentation](https://www.pulumi.com/docs/)
- [Scaleway Documentation](https://www.scaleway.com/en/docs/)
