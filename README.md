[![Garbage Collection](https://github.com/scality/platform-spawner/actions/workflows/gc-cron.yaml/badge.svg)](https://github.com/scality/platform-spawner/actions/workflows/gc-cron.yaml)

# Platform Spawner

A Pulumi program that spawns a platform to test on. One bastion, a handful of
nodes, three networks, and addresses that are the same on every platform.

```bash
pulumi stack init <stack>
pulumi config set instance_image rocky-9
pulumi config set ssh_private_key_create true
pulumi up
ssh -F ssh_config bastion
```

The [quickstart](docs/QUICKSTART.md) takes it from the top, on either cloud.

## Documentation

| Where | What it holds |
|-------|---------------|
| [Quickstart](docs/QUICKSTART.md) | Spawning a platform from your machine, from a clone to a shell on it |
| [Platform](docs/PLATFORM.md) | The machines, the networks and the addresses a platform comes with |
| [GitHub Action](docs/GITHUB_ACTION.md) | Spawning and destroying from a workflow |

## Configuration

A platform is described by the configuration of its stack. Set a key with
`pulumi config set <key> <value>`, or write `Pulumi.<stack>.yaml` directly:

<!-- This is generated with tools/generate_docs.py -->
<!-- BEGIN_PULUMI_DOCS -->
| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| provider | Cloud provider to spawn the platform on | string | `aws` | no |
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
| openstack_external_network | Name of the network providing internet access and floating IPs | string | `Ext-Net` | no |
| openstack_dns_nameservers | Resolvers handed to the instances (OpenStack has no managed resolver) | array | `['8.8.8.8', '8.8.4.4']` | no |
| extra_volumes | Additional volumes to attach to the instances | array | `[]` | no |
<!-- END_PULUMI_DOCS -->

## Contributing

See [contributing](CONTRIBUTING.md) for details.

## Design

See [design](DESIGN.md) for details.
