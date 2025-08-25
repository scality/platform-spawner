[![Garbage Collection](https://github.com/scality/platform-spawner/actions/workflows/gc-cron.yaml/badge.svg)](https://github.com/scality/platform-spawner/actions/workflows/gc-cron.yaml)

# Platform Spawner

A minimal Pulumi template for provisioning cloud resources using Pulumi.

## Prerequisites

- AWS credentials and region configured in your environment
  (for example via AWS CLI or environment variables).
- Python 3.13 or later installed.
- [Pulumi CLI](https://www.pulumi.com/docs/iac/download-install/) installed.
- [uv](https://docs.astral.sh/uv/) installed.

## Getting Started

### Login to pulumi

```bash
pulumi login file://./
```

> **Note**
> To upload your stack state to S3, you can also login to S3 following the
> Pulumi documentation.

### Create a new stack

Create a new stack:

```bash
pulumi stack init <stack-name>
```

### Fill stack configuration

Fill the required configuration values:

```bash
pulumi config set <key> <value>
```

<!-- This is generated with tools/generate_docs.py -->
<!-- BEGIN_PULUMI_DOCS -->
| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| product | Product name for the resources | string | `unknown` | no |
| offline | If true, the platform will not be connected to the internet | boolean | `False` | no |
| authorized_tcp_ports | List of authorized TCP ports for ingress to the instances | array | `[22]` | no |
| authorized_udp_ports | List of authorized UDP ports for ingress to the instances | array | `[]` | no |
| authorized_icmp | Whether ICMP traffic is authorized for ingress to the instances | boolean | `True` | no |
| authorized_cidrs | List of authorized CIDRs for the instances | array | `['141.94.181.72/32', '84.14.13.200/29', '193.248.60.56/32', '38.142.74.18/32', '__my_ip__']` | no |
| instance_image | Image for the instances (e.g.: AMI name for AWS) | string | N/A | yes |
| instance_count | Number of instances to create | integer | `3` | no |
| instance_flavor | Flavor of the instance | string | `medium` | no |
| instance_root_disk_size | Root disk size for the instance (in GiB) | integer | `50` | no |
| bastion_image | Image for the bastion host | string | `rocky-9` | no |
| bastion_flavor | Flavor of the bastion host | string | `small` | no |
| bastion_root_disk_size | Root disk size for the bastion host (in GiB) | integer | `30` | no |
| ssh_key_name | Name of the SSH key to use (either this or ssh_private_key_create must be set) | string | `` | no |
| ssh_private_key_create | If true, a new SSH key will be created (either this or ssh_key_name must be set) | boolean | `False` | no |
| disable_auto_stop | If true, the instance will not be automatically stopped | boolean | `False` | no |
| extra_volumes | Additional volumes to attach to the instances | array | `[]` | no |
<!-- END_PULUMI_DOCS -->

### Spawn the cluster

To see the resources that will be created, run:

```bash
pulumi preview
```

Then to create the resources, run:

```bash
pulumi up
```

### Retrieve output

To retrieve the output values after the resources have been created, run:

```bash
pulumi stack output
```

Or to get it in JSON format:

```bash
pulumi stack output --json
```

### Destroy the cluster

To destroy the resources, run:

```bash
pulumi destroy
```

## Environment information

### Machines

This template deploys, by default, 1 bastion and 3 nodes.

- Bastion has access to nodes networks, so it can be used to run
  some tests when access to networks is required.
- A various number of nodes depending on a configuration
  (default is 3) that can be used to run workloads.

### Network configuration

Every machine has 2 different IPs that are fixed.

We have 3 networks:

- Public network: A private network (``172.30.0.0/24``) that
  has direct access to internet (only available on bastion)
- Control plane network: A private network (``172.30.100.0/24``)
- Workload plane network: A private network (``172.30.200.0/24``)

> **Note**
> In the public network you have a fixed private IP available on
> the host and, on top of it, an elastic IP that come from AWS
> and can be used to access the machine

| Node | Control plane IP | Workload plane IP | Public IP |
|------|------------------|-------------------|-----------|
| Bastion | `172.30.100.99` | `172.30.200.99`  | `172.30.0.99` |
| Node-X    | `172.30.100.10x` | `172.30.200.10x` | |

Which means that by default Node-X are not accessible you have to connect
to the bastion first OR you can use `sshuttle` to access the nodes networks
directly:

```bash
sshuttle -r rocky@<bastion_elastic_ip> 172.30.100.0/24 172.30.200.0/24
```

## Github Actions

### Overview

This repository provides a Github Action to easily spawn and destroy
infrastructures.

### Usage

In order to work this actions needs:

- An action (either `spawn` or `destroy` or 'list')
- AWS credentials
- Artifacts credentials

#### For spawning

In addition to the above credentials, you have to provide:

- A unique stack name
- A configuration to describe what need to be spawned
  (refer to the [fill stack configuration section](#fill-stack-configuration)
  for more information)

#### For destroying

In addition to the above credentials, you have to provide a unique stack name.

#### For listing

In addition to the above credentials, you have to provide an age (in hours).
The action will return the list of stacks older than the given age.

This is useful for garbage collection of old stacks.

#### Details

See [action.yaml](action.yaml) for details.

#### Examples

A full example of usage can be found in
[.github/workflows/e2e-tests.yaml](.github/workflows/e2e-tests.yaml).

For garbage collection of old stacks, you can refer to
[.github/workflows/gc-cron.yaml](.github/workflows/gc-cron.yaml).

## Contributing

See [contributing](CONTRIBUTING.md) for details.

## Design

See [design](DESIGN.md) for details.
