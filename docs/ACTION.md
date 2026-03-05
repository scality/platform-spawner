# GitHub Action Reference

This document provides a comprehensive reference for the `platform-spawner` GitHub Action.

## Overview

The Platform Spawner GitHub Action automates infrastructure deployment in CI/CD pipelines. It supports four operations:

- **spawn**: Create new infrastructure
- **destroy**: Tear down existing infrastructure
- **list**: List stacks older than a specified age
- **setup**: Install dependencies only (no infrastructure changes)

## Quick Start

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

---

## Actions Reference

### spawn

Creates new infrastructure based on the provided configuration.

**Required inputs**: `stack_name`, `configuration`, provider credentials

**Outputs**: `bastion`, `nodes`

### destroy

Destroys existing infrastructure by stack name.

**Required inputs**: `stack_name`, provider credentials

**Outputs**: None

### list

Lists Pulumi stacks older than the specified age.

**Required inputs**: `age`, provider credentials

**Outputs**: `stacks_list`

### setup

Installs dependencies (Pulumi, uv, Python packages) without performing any infrastructure operations.

**Required inputs**: None

**Outputs**: None

---

## Inputs Reference

### Core Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `action` | No | `"spawn"` | Action to perform: `spawn`, `destroy`, `list`, or `setup`. |
| `stack_name` | Yes* | - | Unique name for the Pulumi stack. Required for `spawn` and `destroy`. |
| `configuration` | Yes* | - | YAML configuration for infrastructure. Required for `spawn`. See [Configuration YAML](#configuration-yaml). |
| `product` | No | `""` | Product name prefix for all resources. Falls back to repository name if not set. |

### Provider Credentials

#### Scaleway (Functional)

| Input | Required | Description |
|-------|----------|-------------|
| `scaleway_access_key` | Yes | Scaleway API access key. |
| `scaleway_secret_key` | Yes | Scaleway API secret key. |
| `scaleway_project_id` | Yes | Scaleway project ID. |

#### AWS (Future/Unused)

| Input | Required | Description |
|-------|----------|-------------|
| `aws_access_key_id` | No | AWS access key ID. **Not currently used.** |
| `aws_secret_key` | No | AWS secret key. **Not currently used.** |
| `aws_region` | No | AWS region. **Not currently used.** |

### SSH Configuration

| Input | Required | Default | Status | Description |
|-------|----------|---------|--------|-------------|
| `ssh_key_name` | No | `""` | **NOT IMPLEMENTED** | Name of existing SSH key. Read but not used. |
| `ssh_private_key_create` | No | `"false"` | Functional | Generate a new SSH keypair. |
| `ssh_public_keys` | No | `"[]"` | Functional | JSON array of SSH public keys to inject. |

#### `ssh_public_keys` Examples

Inject SSH public keys for instance access:

```yaml
# Single key
ssh_public_keys: '["ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... user@example.com"]'

# Multiple keys
ssh_public_keys: |
  [
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... user1@example.com",
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... user2@example.com"
  ]

# From previous step output (common pattern)
ssh_public_keys: ${{ steps.ssh-key.outputs.public_key }}
```

#### `ssh_private_key_create` Example

Generate a new SSH keypair automatically:

```yaml
ssh_private_key_create: "true"
# The generated private key will be available in the action outputs
```

### Bastion Configuration

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `bastion_os_name` | No | `"rocky"` | OS family name for the bastion host (e.g., `rocky`, `ubuntu`, `debian`). |
| `bastion_os_major_version` | No | `"9"` | Major OS version for the bastion host (e.g., `9`, `22`). |

### Security Configuration

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `authorized_cidrs` | No | `""` | CIDRs allowed to access gateway SSH bastion. Accepts JSON array or comma-separated string. |
| `custom_routes` | No | `""` | JSON array of custom VPC routes. See [Custom Routes](#custom-routes-format). |

#### `authorized_cidrs` Examples

Restrict SSH bastion access to specific IPs or networks:

```yaml
# JSON array format (recommended)
authorized_cidrs: '["193.248.60.56/32", "10.0.0.0/8"]'

# Comma-separated string format
authorized_cidrs: "193.248.60.56/32,10.0.0.0/8"

# Single IP
authorized_cidrs: '["203.0.113.50/32"]'

# Allow all (default if not specified - not recommended for production)
authorized_cidrs: '["0.0.0.0/0"]'
```

#### `custom_routes` Examples

Route traffic to specific external destinations through the gateway:

```yaml
# Single route
custom_routes: '[{"destination": "35.241.243.135/32", "description": "artifacts.scality.net"}]'

# Multiple routes
custom_routes: |
  [
    {"destination": "35.241.243.135/32", "description": "artifacts.scality.net"},
    {"destination": "217.182.187.84/32", "description": "packages.scality.com"},
    {"destination": "10.100.0.0/16", "description": "corporate-network"}
  ]
```

### Storage Configuration

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `store_to_s3` | No | `"true"` | Store stack output in S3 for garbage collection. |

### List Action Configuration

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `age` | Yes* | - | Age in hours to filter stacks. Required for `list` action. |

### Deprecated Inputs

| Input | Status | Description |
|-------|--------|-------------|
| `artifacts_user` | **COMMENTED OUT** | Artifacts server username. Upload code is disabled. |
| `artifacts_password` | **COMMENTED OUT** | Artifacts server password. Upload code is disabled. |
| `instance_image` | **MOVED** | Now specified in `configuration` YAML instead of as a top-level input. |

---

## Outputs Reference

| Output | Action | Description |
|--------|--------|-------------|
| `bastion` | spawn | Bastion/gateway connection information (JSON). |
| `nodes` | spawn | Deployed nodes information (JSON). |
| `stacks_list` | list | JSON array of stack names older than specified age. |

### Bastion Output Format

The bastion is a VM with a public IP that acts as SSH jump host and NAT gateway:

```json
{
  "type": "vm",
  "ip": "51.159.x.x",
  "port": 22,
  "user": "rocky",
  "private_ip": "192.168.10.1",
  "instance_id": "fr-par-1/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "extra_nics": {
    "storage": {
      "private_ip": "10.1.0.1"
    }
  }
}
```

SSH to a worker node via the bastion:

```bash
ssh -J rocky@<bastion_ip> artesca-os@<node_private_ip>
```

### Nodes Output Format

```json
{
  "my-app-node-01": {
    "id": "fr-par-1/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "name": "my-app-node-01",
    "instance_type": "PRO2-S",
    "private_ip": "192.168.10.2",
    "ssh_command": "ssh -J bastion@51.159.x.x:61000 artesca-os@my-app-node-01.my-app-internal.internal",
    "urn": "urn:pulumi:...",
    "volumes": [
      {
        "id": "...",
        "name": "my-app-node-01-data",
        "size_gb": 500
      }
    ],
    "extra_nics": {
      "storage": {
        "private_ip": "10.1.0.2"
      }
    }
  }
}
```

---

## Configuration YAML

The `configuration` input accepts YAML with infrastructure settings. All fields from the [Configuration Reference](CONFIGURATION.md) are supported.

### Commonly Used Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instance_image` | string | **required** | Image/snapshot ID for instances. |
| `instance_count` | integer | `3` | Number of worker nodes. |
| `instance_flavor` | string | `"medium"` | Instance size flavor. |
| `instance_root_disk_size` | integer | `50` | Root disk size in GiB. |
| `extra_volumes` | list | `[]` | Additional volumes per node. |
| `extra_private_networks` | list | `[]` | Additional private networks. |

#### `instance_flavor` Options

Available instance flavors (maps to Scaleway instance types):

| Flavor | Scaleway Type | vCPUs | RAM | Use Case |
|--------|---------------|-------|-----|----------|
| `tiny` | PLAY2-PICO | 1 | 1GB | Minimal testing |
| `small` | PLAY2-NANO | 2 | 4GB | Testing, bastion hosts |
| `medium` | PRO2-S | 4 | 16GB | Standard workloads |
| `medium-plus` | PRO2-M | 8 | 32GB | Medium workloads |
| `large` | PRO2-L | 16 | 64GB | Production workloads |
| `xlarge` | PRO2-XL | 32 | 128GB | Heavy production workloads |

You can also specify exact Scaleway instance types directly (e.g., `GP1-M`).

#### `extra_volumes` Examples

Attach additional block storage volumes to each instance:

```yaml
# Single data volume per node
extra_volumes:
  - suffix: data
    size: 500      # Size in GB
    count: 1       # Number of volumes with this config

# Multiple volumes for different purposes
extra_volumes:
  - suffix: data
    size: 500
    count: 1
  - suffix: logs
    size: 100
    count: 1

# Many small volumes (e.g., for distributed storage)
extra_volumes:
  - suffix: osd
    size: 100
    count: 12      # Creates 12 volumes: node-01-osd-01, node-01-osd-02, etc.
```

Each volume creates a block device attached to the instance. The `suffix` is used in the volume name: `{node-name}-{suffix}` or `{node-name}-{suffix}-{index}` if count > 1.

#### `extra_private_networks` Examples

Attach instances to additional isolated private networks:

```yaml
# Single extra network for storage traffic
extra_private_networks:
  - suffix: data
    subnet: "192.168.20.0/24"

# Multiple networks for network segregation
extra_private_networks:
  - suffix: data
    subnet: "192.168.20.0/24"    # Data plane traffic
  - suffix: storage
    subnet: "10.1.0.0/24"        # Storage replication traffic
  - suffix: management
    subnet: "172.16.0.0/24"      # Management/monitoring traffic
```

Each network creates:
- A new Scaleway Private Network in the VPC
- A NIC attached to **each instance** (both worker nodes and the bastion VM) with an IP from that subnet

**Note:** The primary internal network (`192.168.10.0/24` by default) is always created. Extra networks are in addition to this.

### Example Configuration

```yaml
configuration: |
  instance_image: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  instance_count: 3
  instance_flavor: medium
  instance_root_disk_size: 100
  extra_volumes:
    - suffix: data
      size: 500
      count: 1
  extra_private_networks:
    - suffix: storage
      subnet: "10.1.0.0/24"
```

---

## Custom Routes Format

Custom routes allow instances to reach specific external destinations through the gateway.

```yaml
custom_routes: |
  [
    {"destination": "35.241.243.135/32", "description": "artifacts.scality.net"},
    {"destination": "217.182.187.84/32", "description": "packages.scality.com"}
  ]
```

---

## Workflow Examples

### Basic Spawn and Destroy

```yaml
name: Deploy Infrastructure

on:
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Generate SSH Key
        id: ssh-key
        run: |
          ssh-keygen -t ed25519 -f /tmp/id_ed25519 -N ""
          echo "public_key=[\"$(cat /tmp/id_ed25519.pub)\"]" >> $GITHUB_OUTPUT

      - name: Spawn cluster
        id: spawn
        uses: scality/platform-spawner@v2
        with:
          action: spawn
          stack_name: test-${{ github.run_number }}
          product: test-${{ github.run_number }}
          configuration: |
            instance_image: ${{ vars.SNAPSHOT_ID }}
            instance_count: 1
            instance_flavor: medium
          ssh_public_keys: ${{ steps.ssh-key.outputs.public_key }}
          scaleway_access_key: ${{ secrets.SCW_ACCESS_KEY }}
          scaleway_secret_key: ${{ secrets.SCW_SECRET_KEY }}
          scaleway_project_id: ${{ secrets.SCW_PROJECT_ID }}

      - name: Show connection info
        run: |
          echo "Bastion: ${{ steps.spawn.outputs.bastion }}"
          echo "Nodes: ${{ steps.spawn.outputs.nodes }}"

      - name: Destroy cluster
        if: always()
        uses: scality/platform-spawner@v2
        with:
          action: destroy
          stack_name: test-${{ github.run_number }}
          scaleway_access_key: ${{ secrets.SCW_ACCESS_KEY }}
          scaleway_secret_key: ${{ secrets.SCW_SECRET_KEY }}
          scaleway_project_id: ${{ secrets.SCW_PROJECT_ID }}
```

### Production Deployment with Security

```yaml
- name: Spawn production cluster
  uses: scality/platform-spawner@v2
  with:
    action: spawn
    stack_name: prod-${{ github.run_number }}
    product: production
    configuration: |
      instance_image: ${{ vars.PROD_SNAPSHOT_ID }}
      instance_count: 6
      instance_flavor: large
      instance_root_disk_size: 200
      extra_volumes:
        - suffix: data
          size: 1000
          count: 4
      extra_private_networks:
        - suffix: storage
          subnet: "10.1.0.0/24"
    ssh_public_keys: ${{ steps.ssh-key.outputs.public_key }}
    authorized_cidrs: "52.161.62.16/28,52.159.241.192/28"
    custom_routes: |
      [{"destination": "35.241.243.135/32", "description": "artifacts.scality.net"}]
    scaleway_access_key: ${{ secrets.SCW_ACCESS_KEY }}
    scaleway_secret_key: ${{ secrets.SCW_SECRET_KEY }}
    scaleway_project_id: ${{ secrets.SCW_PROJECT_ID }}
```

### Multi-Homed Instances

```yaml
- name: Spawn cluster with dual networks
  uses: scality/platform-spawner@v2
  with:
    action: spawn
    stack_name: dual-net-${{ github.run_number }}
    product: dual-net
    configuration: |
      instance_image: ${{ vars.SNAPSHOT_ID }}
      instance_count: 3
      instance_flavor: large
      extra_private_networks:
        - suffix: data
          subnet: "10.1.0.0/24"
        - suffix: storage
          subnet: "10.2.0.0/24"
    ssh_public_keys: ${{ steps.ssh-key.outputs.public_key }}
    scaleway_access_key: ${{ secrets.SCW_ACCESS_KEY }}
    scaleway_secret_key: ${{ secrets.SCW_SECRET_KEY }}
    scaleway_project_id: ${{ secrets.SCW_PROJECT_ID }}
```

### Garbage Collection (List Old Stacks)

```yaml
name: Cleanup Old Stacks

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - name: List stacks older than 24 hours
        id: list
        uses: scality/platform-spawner@v2
        with:
          action: list
          age: 24
          scaleway_access_key: ${{ secrets.SCW_ACCESS_KEY }}
          scaleway_secret_key: ${{ secrets.SCW_SECRET_KEY }}
          scaleway_project_id: ${{ secrets.SCW_PROJECT_ID }}

      - name: Show old stacks
        run: echo "Old stacks: ${{ steps.list.outputs.stacks_list }}"

      - name: Destroy old stacks
        if: steps.list.outputs.stacks_list != '[]'
        run: |
          for stack in $(echo '${{ steps.list.outputs.stacks_list }}' | jq -r '.[]'); do
            echo "Destroying stack: $stack"
            # Add destroy step here
          done
```

---

## Behavior Notes

### S3 Backend

When `store_to_s3: true` (default), the action:

1. Logs in to the Pulumi S3 backend at `s3://artesca-stacks`
2. Stores stack state in S3 for persistence across runs
3. Stores stack output JSON for garbage collection

### SSH Config Generation

After successful spawn, an SSH config file is generated and symlinked to `$GITHUB_WORKSPACE/ssh_config`. Use it with:

```bash
ssh -F ssh_config <node-name>
```

### Step Summary

The action generates a GitHub Step Summary with:

- Configuration used (YAML)
- Spawn output (JSON)

### Environment Variables Set

The action sets these environment variables for subsequent steps:

| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` | S3 access key (for Pulumi backend) |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key |
| `AWS_REGION` | S3 region |
| `SCW_ACCESS_KEY` | Scaleway access key |
| `SCW_SECRET_KEY` | Scaleway secret key |
| `SCW_DEFAULT_PROJECT_ID` | Scaleway project ID |
| `PULUMI_CONFIG_PASSPHRASE` | Empty (for local encryption) |

---

## Troubleshooting

### Stack Already Exists

If spawn fails because the stack already exists:

```yaml
- name: Destroy existing stack first
  uses: scality/platform-spawner@v2
  with:
    action: destroy
    stack_name: my-stack
    # ... credentials
  continue-on-error: true

- name: Spawn new stack
  uses: scality/platform-spawner@v2
  with:
    action: spawn
    stack_name: my-stack
    # ... rest of config
```

### Configuration Errors

Common configuration issues:

| Error | Cause | Solution |
|-------|-------|----------|
| "Configuration must be provided" | Missing `configuration` for spawn | Add `configuration` input |
| "Stack name must be provided" | Missing `stack_name` for spawn/destroy | Add `stack_name` input |
| "Age must be a positive integer" | Invalid `age` for list action | Provide integer value |

### SSH Access Issues

If SSH access fails:

1. Verify `authorized_cidrs` includes your IP
2. Check that SSH keys were properly injected
3. Use the SSH command from the nodes output
4. Verify the bastion gateway is accessible on port 61000
