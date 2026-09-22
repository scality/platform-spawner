# Troubleshooting

## The SSH files are gone

A spawn writes the `ssh_config`, the `known_hosts` and, when it generated one,
the SSH key, where it ran. Another machine, or the same one after a clean up,
has nothing left to reach the platform with. Write them out of the stack:

```bash
uv run tools/get_ssh_config.py
```

Everything it needs is in the stack. The addresses and the users are exported,
and so is the key a spawn generated, as a secret. Nothing deployed is read or
touched, so this works just as well on a platform someone else spawned.

A platform running on a key of your own is reported as such. That key is yours
to point at.

## A failed spawn left ports behind

A cloud that goes down mid-spawn can answer the call that creates a port and
then not the one that waits for it. The port exists and the stack never
learned of it. Every address here is fixed, so that port holds the one the
next attempt needs: spawning again answers `IpAddressAlreadyAllocated`, and
destroying answers that the subnet still has an allocation, which leaves the
platform running and unremovable.

```bash
uv run --group snapshot tools/clean_orphan_ports.py
```

Only a port of ours, on a network of ours, that nothing is using and that the
stack does not know about. Whatever a router, the DHCP agent or an instance
holds is left alone. The action runs it between two attempts, so a spawn or a
destroy that trips over one recovers on its own.

## Work against another state backend

Pulumi keeps its state wherever it was last told to, and that choice is global
to your machine rather than to this project. `pulumi login` remembers each
backend it has seen, so moving between them costs nothing:

```bash
pulumi login --interactive    # pick among the backends already known
```

A single command can be pointed elsewhere without disturbing that choice. That
is what you want when most of your work sits on one backend, the platforms
spawned by CI on another:

```bash
PULUMI_BACKEND_URL="file://./" pulumi stack ls
```

The tools go through the same CLI, so the variable reaches them too.
