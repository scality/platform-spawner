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
| `instance_image` | string | `"rockylinux_9"` | Image for worker instances. Accepts a Scaleway marketplace label (e.g., `rockylinux_9`), a user-friendly alias (e.g., `rocky-9`), or a image UUID. See [Image Resolution](#image-resolution) below. |
| `instance_snapshot` | string | `""` | Snapshot UUID to boot worker instances from. When set, overrides `instance_image`. |
| `instance_flavor` | string | `"medium"` | Abstract flavor name mapped to provider-specific instance type. See [Flavor Reference](#flavor-reference) below. |
| `instance_root_disk_size` | integer | `50` | Root disk size in GiB for worker instances. |
| `disable_auto_stop` | boolean | `false` | **NOT IMPLEMENTED** - This field is read but has no effect. |

### CLI Example

```bash
pulumi config set instance_flavor "large"
pulumi config set instance_root_disk_size 100
```

### Image Resolution

The spawner resolves instance images differently depending on the input format and instance type:

| Input | Resolved As | Example |
|-------|-------------|--------|
| Marketplace label | Used directly for block-storage instances (PLAY2, PRO2) | `rockylinux_9` |
| User-friendly alias | Mapped to marketplace label (`rocky` → `rockylinux`) | `rocky-9` → `rockylinux_9` |
| Snapshot UUID | Boot volume created from snapshot | `fc979535-d07c-43b4-8c33-d8f483484d16` |

**Bastion node**: Always uses the marketplace label format (e.g., `rockylinux_9`) built from the `bastion_os_name` and `bastion_os_major_version` fields. The bastion runs on `PLAY2-NANO` (block-storage-only), which requires marketplace labels rather than UUIDs.

**Worker nodes**: Can use either marketplace labels or snapshot UUIDs. When `instance_snapshot` is set, it takes priority and the spawner creates a boot volume from the snapshot.

#### OS name aliases

For the `bastion_os_name` field, the following aliases are automatically mapped to Scaleway marketplace label names:

| Alias | Marketplace Name |
|-------|------------------|
| `rocky` | `rockylinux` |
| `rocky-linux` | `rockylinux` |
| `ubuntu` | `ubuntu` |
| `debian` | `debian` |

For example, `bastion_os_name: rocky` with `bastion_os_major_version: 9` resolves to the marketplace label `rockylinux_9`.

#### Dynamic image lookup

The `images.py` module provides functions to look up the latest marketplace image UUID for a given OS and version. Supported OS families:

- **Rocky Linux**: `rockylinux` (e.g., `rockylinux_8`, `rockylinux_9`)
- **Ubuntu**: `ubuntu` (e.g., `ubuntu_jammy`, `ubuntu_22.04`)
- **Debian**: `debian` (e.g., `debian_11`)

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

## Placement Group

All instances in a deployment (bastion + worker nodes) can be placed in a shared **placement group** to ensure optimal network performance.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `placement_group_policy_mode` | string | `"optional"` | Placement group policy mode. Options: `"optional"` (recommended) or `"enforced"`. When set to `"optional"`, instances will use the placement group if capacity allows, but deployment will succeed even if the constraint cannot be satisfied. When set to `"enforced"`, deployment may fail if Scaleway cannot co-locate all instances. |

**Policy Type**: All placement groups use `low_latency` policy type, which co-locates instances on the same hypervisor cluster for minimal network latency.

**Naming**: Every deployment creates exactly one placement group named `{product}-pg` (or `placement-group` when no product is set). The group is created automatically; no user action is required.

### CLI Example

```bash
# Use optional mode (default, recommended)
pulumi config set placement_group_policy_mode "optional"

# Use enforced mode (may block deployment if capacity is insufficient)
pulumi config set placement_group_policy_mode "enforced"
```

### GitHub Action Example

```yaml
configuration: |
  placement_group_policy_mode: optional
```

---

## Bastion Configuration

The bastion is a small VM with a public IP that acts as an SSH jump host and NAT gateway for worker instances.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bastion_os_name` | string | `"rocky"` | OS family name for the bastion host. Mapped to the provider marketplace label via `OS_NAME_ALIASES` (e.g., `rocky` → `rockylinux`). |
| `bastion_os_major_version` | string | `"9"` | Major OS version for the bastion host (e.g., `"9"`, `"22"`). Combined with `bastion_os_name` to form the marketplace label (e.g., `rockylinux_9`). |
| `bastion_flavor` | string | `"small"` | Abstract flavor name for the bastion instance. Mapped via `FLAVOR_MAP` (e.g., `small` → `PLAY2-NANO`). |
| `bastion_root_disk_size` | integer | `30` | Root disk size in GiB for the bastion host. |

### Bastion Services

The bastion VM is automatically configured at boot (via cloud-init) to provide the following services to the cluster:

| Service | Software | Description |
|---------|----------|-------------|
| **NAT Gateway** | iptables | Masquerades outbound traffic from private worker nodes through the bastion's public interface. |
| **NTP Server** | chrony | Serves time to all worker nodes. Syncs upstream from `pool.ntp.org`, then acts as a local stratum 10 NTP source for the `192.168.0.0/16` range. |
| **DNS Resolver** | dnsmasq | Provides DNS resolution to all worker nodes. Captures upstream resolvers at boot, caches queries locally (1000 entries), and prevents `resolv.conf` from being overwritten by NetworkManager. |

Worker nodes are automatically configured to use the bastion's private IP for both DNS and NTP:

- `/etc/resolv.conf` → `nameserver <bastion_private_ip>`
- `/etc/chrony.conf` → `server <bastion_private_ip> iburst`

This eliminates the need for post-deployment SSH steps to configure DNS and NTP — everything runs automatically at instance creation.

### CLI Example

```bash
# Use Ubuntu 22 as bastion OS
pulumi config set bastion_os_name ubuntu
pulumi config set bastion_os_major_version 22

# Use a larger bastion instance
pulumi config set bastion_flavor medium
```

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
| `extra_private_networks` | JSON/YAML list | `[]` | List of private network configurations. Each network is attached to **all** instances — both worker nodes and the bastion. |

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

> **Note:** Extra private networks are attached to **all** instances in the cluster — both worker nodes and the bastion VM. This allows the bastion to also route or monitor traffic on those networks.

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
