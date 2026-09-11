# Quickstart

Spawn a platform from your machine, on OVH Public Cloud (OpenStack) or on
AWS, connect to it, then take it down.

Spawning from a workflow is [another story](GITHUB_ACTION.md).

## What you get

One bastion and three nodes, on addresses that are fixed and the same on every
platform. Only the bastion is reachable from the outside, and the nodes are
reached through it. [PLATFORM.md](PLATFORM.md) has the whole picture.

## 1. Install the tools

- [Pulumi CLI](https://www.pulumi.com/docs/iac/download-install/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.13 or later, which `uv python install 3.13` provides
- `ssh`

The [devcontainer](../.devcontainer/) comes with all of them.

Every command below runs from the root of a clone, the directory holding
`Pulumi.yaml`:

```bash
git clone git@github.com:scality/platform-spawner.git
cd platform-spawner
```

## 2. Get cloud credentials

### OVH Public Cloud (OpenStack)

1. In the OVH Manager, open your Public Cloud project.
2. Create an OpenStack user, or ask your team for one. It needs rights on
   compute, network, block storage and images.
3. Download the OpenStack RC file (Keystone v3) of the region you want.
4. Load it. It asks for the password of the user:

   ```bash
   source ./openrc.sh
   ```

The RC file sets the `OS_*` variables, and only for the shell that loaded it.
Load it again in every new one.

### AWS

Log in the way your team does, with SSO for example:

```bash
aws sso login --profile <profile>
export AWS_PROFILE=<profile>
aws sts get-caller-identity
```

The region is part of the stack configuration, in step 5.

## 3. Choose where Pulumi keeps the state

The state is everything Pulumi knows of the platform. Destroying one needs
its state, so put it somewhere that will still be there when you are done:

```bash
pulumi login file://./
export PULUMI_CONFIG_PASSPHRASE=''
```

This keeps it in `.pulumi/`, inside the clone. Do not remove the clone before
you have destroyed the platform, or the resources are left to be taken away
by hand. `pulumi login --local` keeps the state under `~/.pulumi` instead,
where deleting the clone leaves it alone.

The passphrase encrypts the secrets of the state, the generated SSH key among
them. An empty one is fine for a platform nobody else will reach. Whatever
you pick, export it in every shell that touches the stack.

## 4. Create a stack

A stack is one platform. Name it after yourself, so that two of them never
answer to the same name:

```bash
pulumi stack init <you>-dev
```

## 5. Configure the stack

The smallest configuration that spawns something, on OVH Public Cloud:

```bash
pulumi config set provider openstack
pulumi config set product <you>
pulumi config set instance_image rocky-9
pulumi config set instance_count 1
pulumi config set ssh_private_key_create true
```

> **Note**
> The OpenStack provider needs a network providing internet access and
> floating IPs, which is `Ext-Net` on OVH Public Cloud. Set
> `openstack_external_network` if your cloud names it differently.

The same on AWS, which needs a region of its own:

```bash
pulumi config set provider aws
pulumi config set aws:region eu-north-1
pulumi config set product <you>
pulumi config set instance_image rocky-9
pulumi config set instance_count 1
pulumi config set ssh_private_key_create true
```

| Key | Why |
|-----|-----|
| `provider` | Which cloud to spawn on. `aws` is the default. |
| `aws:region` | Where an AWS platform goes. `rocky-9` is only known there in `eu-north-1` and `us-west-2`. |
| `product` | Prefixes the names of the resources. Two platforms sharing a product and a stack name collide. |
| `instance_image` | What the nodes boot on, an AMI name on AWS and a Glance image name on OpenStack. It has no default. |
| `instance_count` | One node is enough to see it work, three is the default. |
| `ssh_private_key_create` | Generates a key for this platform. The other way is `ssh_key_name`, a key the cloud already holds, which then has to be in your `ssh-agent`. |

An image that is not one of the `rocky-*` ones has to say who to log in as,
since nothing else names the user:

```bash
pulumi config set instance_ssh_user <user>
```

`bastion_ssh_user` does the same for the bastion, which runs `bastion_image`
rather than the image of the nodes.

Every key is in the [configuration reference](../README.md#configuration).
The ones worth knowing early:

| Key | Default | What it does |
|-----|---------|--------------|
| `instance_flavor` | `medium` | `small`, `medium`, `large` or `xlarge`. |
| `instance_root_disk_size` | `50` | Root disk of a node, in GiB. AWS only, since the flavor decides it on OpenStack. |
| `bastion_flavor` | `small` | Same sizes as `instance_flavor`. |
| `authorized_cidrs` | `['__my_ip__']` | Who may reach the bastion. `__my_ip__` stands for the public address of the machine spawning. |
| `offline` | `false` | `true` cuts the nodes off the internet, and the bastion keeps it. |
| `extra_volumes` | none | Extra disks on every node. |
| `extra_networks` | none | Extra isolated networks, on every machine. See [PLATFORM.md](PLATFORM.md#extra-networks). |

These commands write `Pulumi.<stack>.yaml`. Writing that file directly is
easier for the keys taking a list:

```yaml
config:
  platform-spawner:provider: openstack
  platform-spawner:product: jdoe
  platform-spawner:instance_image: rocky-9
  platform-spawner:instance_count: 3
  platform-spawner:instance_flavor: large
  platform-spawner:ssh_private_key_create: true
  platform-spawner:extra_volumes:
  - size: 10
    count: 2
```

## 6. Spawn

```bash
pulumi preview   # what it would create
pulumi up        # create it
```

It takes a few minutes. The command only returns once every machine answers
SSH and cloud-init is done with it. A finished update is a platform ready to
be used.

## 7. Connect

A spawn writes its SSH files beside `Pulumi.yaml`:

| File | What it is |
|------|------------|
| `ssh_config-<stack>` | The configuration of that platform |
| `ssh_config` | A link to the platform spawned last |
| `ssh_<product>_<stack>` and `.pub` | The generated key, when `ssh_private_key_create` is set |

```bash
ssh -F ssh_config bastion          # the platform spawned last
ssh -F ssh_config-<stack> node-1   # jumps through the bastion on its own
```

To reach the node networks from your machine rather than from the bastion,
`sshuttle` carries them over:

```bash
sshuttle -r <user>@<bastion public IP> 172.30.100.0/24 172.30.200.0/24
```

The addresses, and everything else the platform reports:

```bash
pulumi stack output --json
```

## 8. Change the platform

Set the key and spawn again. Only what the change touches is replaced:

```bash
pulumi config set offline true
pulumi up
```

## 9. Destroy

Nothing takes a platform away on its own, and it is billed until it goes:

```bash
pulumi destroy
pulumi stack rm <you>-dev
```

The key generated for the platform stays on disk. Throwing a private key away
is for someone to decide, so remove it once you are sure:

```bash
rm -f ssh_<product>_<stack> ssh_<product>_<stack>.pub
```

## Cheat sheet

```bash
pulumi stack ls              # the stacks of this backend
pulumi stack select <stack>  # work on another one
pulumi config                # the configuration of the current one
pulumi stack output --json   # addresses and ids
pulumi up                    # create, or bring in line with the configuration
pulumi destroy               # take it away
```
