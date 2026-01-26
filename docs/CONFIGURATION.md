# Configuration Reference

This document provides a comprehensive reference for all configurable fields in Platform Spawner.

## Overview

Platform Spawner can be configured in two ways:

1. **CLI Usage (Pulumi Config)**: Set values using `pulumi config set <key> <value>`
2. **GitHub Action (YAML)**: Provide configuration via the `configuration` input

Both methods use the same underlying field names. This reference documents all available options.

---

## Required Configuration

These fields must be provided for any deployment.

| Field | Type | Description |
|-------|------|-------------|
| `instance_count` | integer | Number of worker instances to deploy. Must be >= 1. |
| `project_id` | string | Cloud provider project ID (Scaleway Project ID). |
| `instance_image` | string | Image/snapshot ID for worker instances. Can be a Scaleway snapshot UUID or marketplace image label. |

### CLI Example

```bash
pulumi config set instance_count 3
pulumi config set project_id "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
pulumi config set instance_image "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### GitHub Action Example

```yaml
configuration: |
  instance_count: 3
  instance_image: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

---

## Global Configuration

These fields control naming and provider selection.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `product` | string | `"unknown"` | Product name prefix applied to all resource names (VPC, gateway, nodes, etc.). |
| `provider` | string | `"scaleway"` | Cloud provider to use. Currently only `scaleway` is supported. |
| `region` | string | `"fr-par"` | Provider region for resource deployment. |
| `zone` | string | `"fr-par-1"` | Provider availability zone within the region. |

### CLI Example

```bash
pulumi config set product "my-app"
pulumi config set provider "scaleway"
pulumi config set region "fr-par"
pulumi config set zone "fr-par-1"
```

### Available Regions and Zones (Scaleway)

| Region | Zones | Location |
|--------|-------|----------|
| `fr-par` | `fr-par-1`, `fr-par-2`, `fr-par-3` | Paris, France |
| `nl-ams` | `nl-ams-1`, `nl-ams-2` | Amsterdam, Netherlands |
| `pl-waw` | `pl-waw-1`, `pl-waw-2` | Warsaw, Poland |

---

## Instance Configuration

These fields control worker instance sizing and behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instance_flavor` | string | `"medium"` | Abstract flavor name mapped to provider-specific instance type. See [Flavor Reference](#flavor-reference) below. |
| `instance_root_disk_size` | integer | `50` | Root disk size in GiB for worker instances. |
| `disable_auto_stop` | boolean | `false` | **NOT IMPLEMENTED** - This field is read but has no effect. |

### CLI Example

```bash
pulumi config set instance_flavor "large"
pulumi config set instance_root_disk_size 100
```

### Flavor Reference

Abstract flavors are mapped to provider-specific instance types:

| Flavor | Scaleway Type | vCPUs | RAM | Use Case |
|--------|---------------|-------|-----|----------|
| `tiny` | `PLAY2-PICO` | 1 | 1 GB | Minimal testing |
| `small` | `PLAY2-NANO` | 2 | 2 GB | Bastion, light workloads |
| `medium` | `PRO2-S` | 4 | 8 GB | Development, small production |
| `medium-plus` | `PRO2-M` | 8 | 16 GB | Production |
| `large` | `PRO2-L` | 16 | 32 GB | High-performance |
| `xlarge` | `PRO2-XL` | 32 | 64 GB | Heavy workloads |
| `gp-small` | `GP1-XS` | - | - | General purpose (small) |
| `gp-medium` | `GP1-S` | - | - | General purpose (medium) |
| `gp-large` | `GP1-M` | - | - | General purpose (large) |
| `gp-xlarge` | `GP1-L` | - | - | General purpose (xlarge) |

You can also specify exact Scaleway instance types directly (e.g., `PRO2-XXS`).

---

## Gateway Configuration

The Public Gateway provides SSH bastion functionality and NAT for worker instances.

> **Note**: Previous versions used a dedicated bastion VM. The current architecture uses Scaleway's Public Gateway with built-in SSH bastion feature, making some fields obsolete.

| Field | Type | Default | Status | Description |
|-------|------|---------|--------|-------------|
| `bastion_image` | string | `"rocky-9"` | Functional | Image identifier for marketplace lookup (format: `os-version`). Used internally. |
| `bastion_flavor` | string | `"small"` | **UNUSED** | Gateway uses fixed `VPC-GW-M` type. This field has no effect. |
| `bastion_root_disk_size` | integer | `30` | **NOT IMPLEMENTED** | Gateway is managed by Scaleway. This field has no effect. |

---

## Network Configuration

These fields control network behavior and security.

| Field | Type | Default | Status | Description |
|-------|------|---------|--------|-------------|
| `offline` | boolean | `false` | Functional | Disable NAT/masquerade. When `true`, instances have no internet access. |
| `authorized_cidrs` | list | `["0.0.0.0/0"]` | Functional | CIDRs allowed to access gateway SSH bastion. **Critical for production security.** |
| `custom_routes` | JSON string | `""` | Functional | Custom VPC routes through gateway for specific destinations. |
| `authorized_tcp_ports` | list | `[22]` | **NOT IMPLEMENTED** | Read but not applied. Security groups are hardcoded. |
| `authorized_udp_ports` | list | `[]` | **NOT IMPLEMENTED** | Read but not applied. Security groups are hardcoded. |
| `authorized_icmp` | boolean | `true` | **NOT IMPLEMENTED** | Read but not applied. Security groups are hardcoded. |

### CLI Example

```bash
# Restrict bastion access to specific IPs (recommended for production)
pulumi config set authorized_cidrs '["203.0.113.10/32", "198.51.100.0/24"]'

# Enable offline mode (no internet for instances)
pulumi config set --type bool offline true

# Add custom routes for specific destinations
pulumi config set custom_routes '[{"destination": "35.241.243.135/32", "description": "artifacts.scality.net"}]'
```

### Custom Routes Format

Custom routes allow private instances to reach specific external hosts through the gateway.

```json
[
  {
    "destination": "35.241.243.135/32",
    "description": "artifacts.scality.net"
  },
  {
    "destination": "217.182.187.84/32",
    "description": "packages.scality.com"
  }
]
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `destination` | string | Yes | CIDR block for the route destination. |
| `description` | string | No | Human-readable description for the route. |

---

## SSH Configuration

These fields control SSH key management for instance access.

| Field | Type | Default | Status | Description |
|-------|------|---------|--------|-------------|
| `ssh_key_name` | string | `""` | **NOT IMPLEMENTED** | Name of existing SSH key. Read and logged but not used. |
| `ssh_private_key_create` | boolean | `false` | Functional | Generate a new ED25519 SSH keypair. Key is registered in IAM and injected via cloud-init. |
| `ssh_public_keys` | list | `[]` | Functional | SSH public keys to register in IAM and inject via cloud-init. |

### SSH Key Options

There are four ways to configure SSH access:

| Option | Config | Behavior |
|--------|--------|----------|
| **Default** | *(none)* | Scaleway automatically provides all IAM keys to instances. |
| **Existing key** | `ssh_key_name` | **NOT IMPLEMENTED** - Use option 1, 3, or 4 instead. |
| **Generate new** | `ssh_private_key_create: true` | Generates ED25519 keypair, registers in IAM, injects via cloud-init. |
| **Provide keys** | `ssh_public_keys: [...]` | Registers provided keys in IAM and injects via cloud-init. |

### CLI Example

```bash
# Option 3: Generate new keypair
pulumi config set --type bool ssh_private_key_create true

# Option 4: Provide SSH public keys
pulumi config set ssh_public_keys '["ssh-ed25519 AAAA... user@host"]'
```

---

## Extra Resources

These fields configure additional volumes and networks for worker instances.

### Extra Volumes

Attach additional block storage volumes to each worker instance.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `extra_volumes` | JSON/YAML list | `[]` | List of volume configurations to attach to each worker. |

#### Volume Configuration Format

```json
[
  {"suffix": "service", "size": 120},
  {"suffix": "data", "size": 10, "count": 12}
]
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `suffix` | string | No | `"data"` | Identifier suffix for the volume name. |
| `size` | integer | Yes | - | Volume size in GB. |
| `count` | integer | No | `1` | Number of volumes to create with this configuration. |

**Naming Convention**: `{product}-node-{index}-{suffix}` or `{product}-node-{index}-{suffix}-{num}` when count > 1.

#### CLI Example

```bash
# Single service volume (120GB) + 12 data volumes (10GB each)
pulumi config set extra_volumes '[{"suffix": "service", "size": 120}, {"suffix": "data", "size": 10, "count": 12}]'
```

### Extra Private Networks

Attach additional private network interfaces for multi-homed instances.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `extra_private_networks` | JSON/YAML list | `[]` | List of private network configurations. |

#### Private Network Configuration Format

```json
[
  {"suffix": "data", "subnet": "10.1.0.0/24"},
  {"suffix": "storage", "subnet": "10.2.0.0/24"}
]
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `suffix` | string | No | `"extra"` | Identifier suffix for the network name. |
| `subnet` | string | Yes | - | CIDR block for the private network. |
| `count` | integer | No | `1` | Number of NICs per network (typically 1). |

#### Use Cases

- **Network Isolation**: Separate management traffic from data traffic.
- **Storage Networks**: Dedicated network for storage replication.
- **Multi-Tenancy**: Isolated networks for different applications.
- **High Availability**: Redundant network paths.

#### CLI Example

```bash
# Add data and storage networks
pulumi config set extra_private_networks '[{"suffix": "data", "subnet": "10.1.0.0/24"}, {"suffix": "storage", "subnet": "10.2.0.0/24"}]'
```

---

## Provider-Specific Reference

### Scaleway Instance Types

| Category | Types |
|----------|-------|
| Development | `PLAY2-PICO`, `PLAY2-NANO`, `PLAY2-MICRO` |
| Production | `PRO2-XXS`, `PRO2-XS`, `PRO2-S`, `PRO2-M`, `PRO2-L` |
| General Purpose | `GP1-XS`, `GP1-S`, `GP1-M`, `GP1-L`, `GP1-XL` |

### Scaleway Gateway Types

| Type | Description |
|------|-------------|
| `VPC-GW-S` | Small gateway |
| `VPC-GW-M` | Medium gateway (default) |

---

## Complete Configuration Example

### CLI (Pulumi Config)

```bash
# Required
pulumi config set instance_count 3
pulumi config set project_id "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
pulumi config set instance_image "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# Global
pulumi config set product "my-app"
pulumi config set region "fr-par"
pulumi config set zone "fr-par-1"

# Instance
pulumi config set instance_flavor "medium"
pulumi config set instance_root_disk_size 100

# Network
pulumi config set authorized_cidrs '["203.0.113.10/32"]'

# SSH
pulumi config set --type bool ssh_private_key_create true

# Extra resources
pulumi config set extra_volumes '[{"suffix": "data", "size": 500}]'
pulumi config set extra_private_networks '[{"suffix": "storage", "subnet": "10.1.0.0/24"}]'
```

### GitHub Action (YAML)

```yaml
configuration: |
  instance_count: 3
  instance_image: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  instance_flavor: medium
  instance_root_disk_size: 100
  extra_volumes:
    - suffix: data
      size: 500
  extra_private_networks:
    - suffix: storage
      subnet: "10.1.0.0/24"
```
