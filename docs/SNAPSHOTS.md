# Snapshots

A platform can be captured as one image per instance, and spawned back from
them later. The images outlive the platform they came from. Taking them is a
tool of its own rather than part of an update, since a destroy would otherwise
take them away with everything else.

> **Note**
> OpenStack only for the moment.

## Take one

```bash
uv run --group snapshot tools/generate_snapshot.py <name>
```

Every instance is stopped, captured as `<product>-<name>-node-<n>`, then
started back. The bastion is left out, and so are the extra volumes. Only the
instances themselves are captured.

## Spawn a platform back from it

```bash
pulumi config set restore_snapshot <name>
pulumi up
```

The `product` and the number of instances have to match those the snapshot was
taken with, since each instance comes back from the image taken of it.
`instance_ssh_user` has to be given as well: a snapshot names no image, so
nothing is left to work out who to log in as.

## Take the images away

```bash
uv run --group snapshot tools/delete_snapshot.py --product <product> <name>
```

Nothing else ever will. Destroying the platform a snapshot came from leaves it
alone, which is the whole point of having one.
