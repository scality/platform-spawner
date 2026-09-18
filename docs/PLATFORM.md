# The platform

One bastion and three nodes by default, on three networks. Every address is
fixed, and the same on every platform.

```text
                       internet
                          |
         public IP (an elastic IP on AWS, a floating IP on OpenStack)
                          |
     +--------------------+-------------------+
     | bastion                                |
     |   public          172.30.0.99          |
     |   control plane   172.30.100.99        |
     |   workload plane  172.30.200.99        |
     +--------------------+-------------------+
                          |
     +--------------------+-------------------+
     | node-1   172.30.100.101  172.30.200.101|
     | node-2   172.30.100.102  172.30.200.102|
     | node-3   172.30.100.103  172.30.200.103|
     +----------------------------------------+
```

## Machines

### The bastion

The bastion sits on the three networks, and it is the only machine reachable
from the outside. Whatever needs to speak to the nodes from close by runs
there.

It carries a key and an `ssh_config` of its own, so the nodes are one `ssh`
away from there too. That key belongs to the bastion alone: the instances are
told to trust it, and the key opening the platform never leaves for them.

### The nodes

The nodes run the workloads. `instance_count` says how many there are, three
by default.

## Networks

| Network | CIDR | What it is |
|---------|------|------------|
| Public | `172.30.0.0/24` | The way in and the way out. Only the bastion sits on it. |
| Control plane | `172.30.100.0/24` | Private, routed nowhere. |
| Workload plane | `172.30.200.0/24` | Private, with a way out to the internet unless `offline` is set. |

Every machine holds a fixed address on each network it sits on. The bastion
also carries a public IP handed out by the cloud, which is the one address of
a platform nobody can guess beforehand.

| Machine | Public | Control plane | Workload plane |
|---------|--------|---------------|----------------|
| bastion | `172.30.0.99` | `172.30.100.99` | `172.30.200.99` |
| node-X | | `172.30.100.10x` | `172.30.200.10x` |

The nodes carry no public address. Reaching one goes through the bastion,
which the `ssh_config` of a spawn does on its own. See
[QUICKSTART.md](QUICKSTART.md#7-connect).

## Extra networks

`extra_networks` adds isolated networks of the same kind, attached to every
machine. Their address spaces are not configured. The Nth one is
`172.30.N.0/24`, beside the public network and clear of the two planes, so
nothing has to be picked and nothing can overlap.

Marking one `redundant` gives each instance a second interface on it, which is
what makes a bonding setup testable. The two are numbered a hundred apart:
node-X sits at `.10x` and at `.20x`. The bastion keeps a single interface on
them either way, at `.99` like everywhere else.

How many of them a machine can take is a property of its flavor rather than of
this list. A flavor caps the interfaces an instance carries, a handful on the
smaller ones, so the cloud refuses the spawn long before the address space runs
out.

Each one is called `extra-network-<position>` unless it is given a `name`,
which is what the interfaces and the reported addresses are keyed on. The name
is a label only: a network is addressed by its position in the list, so
renaming one leaves it where it was and reordering the list moves it.

```yaml
extra_networks:
  - name: storage          # 172.30.1.0/24
  - name: bonded           # 172.30.2.0/24
    redundant: true
  - {}                     # 172.30.3.0/24, called extra-network-3
```
