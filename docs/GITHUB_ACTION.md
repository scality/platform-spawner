# The GitHub Action

This repository is a GitHub Action. It spawns and destroys platforms from a
workflow, on the same configuration a spawn by hand takes.

```yaml
- uses: scality/platform-spawner@main
  with:
    action: spawn
    stack_name: ${{ github.run_id }}
    configuration: |
      instance_image: rocky-9
      instance_count: 1
      ssh_private_key_create: true
    artifacts_user: ${{ secrets.ARTIFACTS_USER }}
    artifacts_password: ${{ secrets.ARTIFACTS_PASSWORD }}
```

Whatever it is asked to do, it takes:

| Input | Default | What it is |
|-------|---------|------------|
| `action` | `spawn` | What to do: `spawn`, `snapshot`, `delete-snapshot`, `destroy` or `list` |
| `max_attempts` | `3` | How many times a spawn or a destroy is tried before giving up, since a cloud is not always reachable on the first go |
| `store_to_s3` | `true` | Whether the state of the stack goes to the S3 bucket a garbage collection reads |

The credentials of the cloud are not inputs. They go in the environment of the
job, and they are the ones
[step 2 of the quickstart](QUICKSTART.md#2-get-cloud-credentials) sets up.

> **Note**
> AWS credentials are needed on top of the provider ones whenever
> `store_to_s3` is enabled, since the stack state lives in an S3 bucket.

## Spawning

| Input | Required | What it is |
|-------|----------|------------|
| `stack_name` | yes | The name of the stack, which nothing else may answer to |
| `configuration` | yes | The platform to spawn, as YAML. Its keys are those of the [configuration reference](../README.md#configuration) |
| `product` | no | What the platform belongs to, and what its snapshots are found under. The name of the repository by default |
| `artifacts_user` | yes | The user publishing the artifacts of the spawn |
| `artifacts_password` | yes | The password of that user |

It answers with `bastion` and `nodes`, what the platform reports of its
machines, as JSON.

## Destroying

| Input | Required | What it is |
|-------|----------|------------|
| `stack_name` | yes | The stack to take away |

## Snapshotting

| Input | Required | What it is |
|-------|----------|------------|
| `stack_name` | yes | The stack holding the platform to capture |
| `snapshot_name` | yes | The name to capture it under |

The images are named under the `product` the stack carries, so nothing has to
say it again here. What a snapshot is made of is in
[SNAPSHOTS.md](SNAPSHOTS.md).

## Deleting a snapshot

| Input | Required | What it is |
|-------|----------|------------|
| `snapshot_name` | yes | The snapshot to take away |
| `product` | no | The product the platform was spawned under |

Nothing else ever takes a snapshot away, so whoever took it says when it goes.
The stack is not asked for, since it is usually gone by then. A snapshot is
found under the `product` the platform was spawned with, so the same one has
to be given to both, or left out of both to take the name of the repository.

## Listing

| Input | Required | What it is |
|-------|----------|------------|
| `age` | yes | An age in hours |

It answers with `stacks_list`, the stacks older than that age. This is what a
garbage collection runs on.

## Details

[action.yaml](../action.yaml) holds every input and what it does.

A workflow using all of it is
[e2e-tests.yaml](../.github/workflows/e2e-tests.yaml), and the garbage
collection is [gc-cron.yaml](../.github/workflows/gc-cron.yaml).
