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
| `action` | `spawn` | What to do: `spawn`, `snapshot`, `destroy` or `list` |
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

What a snapshot is made of is in [SNAPSHOTS.md](SNAPSHOTS.md).

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
