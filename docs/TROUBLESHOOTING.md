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

## A failed spawn left something behind

A cloud that goes down mid-spawn can answer the call that does the work and
then not the one that waits for it. What was asked for exists, the stack never
learned of it, and the next attempt walks straight into it.

```bash
uv run --group snapshot tools/clean_orphans.py
```

Two kinds of leftover get a platform stuck for good:

- A port holds a fixed address, and every address here is fixed, so it holds
  the one the next attempt needs. Spawning again answers
  `IpAddressAlreadyAllocated`, and destroying answers that the subnet still
  has an allocation.
- A volume attachment holds its volume. Attaching again answers that the
  volume is already attached, and destroying cannot delete a volume that is in
  use. The volume is detached rather than taken into the stack, so the next
  attempt makes the attachment itself.

Only what the stack owns and does not know about is touched: a port on a
network of ours, a volume of ours the stack holds no attachment for. Whatever
the cloud itself holds, its routers and its DHCP agents, is left alone. The
action runs it between two attempts, so a spawn or a destroy that trips over
one recovers on its own.

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
