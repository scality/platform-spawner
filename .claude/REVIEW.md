# Code Review Criteria

When reviewing pull requests in this repository, check the following areas:

| Area | What to check |
| ---- | ------------- |
| Live platform updates | An `update` must not replace a machine unless asked to. Watch for changed inputs that force a replacement, renamed resources without `aliases`, and removed `ignore_changes` (a machine keeps its image, see `DESIGN.md`). Switching `offline` must never touch an instance. |
| Provider parity | A configuration key or behaviour added to one provider is handled by the other, or refused with an explicit error as `IMAGE_UPLOAD_UNSUPPORTED` does. Provider-specific logic stays in `providers/`, behind `BaseProvider`. Remaining differences are listed in `DESIGN.md`. |
| Configuration schema | Every key in `Pulumi.yaml` has a type, a description and a default. The README table is regenerated with `tools/generate_docs.py`, never edited by hand. Changing a default changes every platform spawned by every caller of the action. Removing or renaming a key breaks existing stacks. |
| Composite action | Inputs reach `run:` scripts through `env:`, never through `${{ }}` interpolation in the script. New inputs are validated in the check steps at the top. Inputs, outputs and stack outputs (`bastion`, `nodes`, `ssh_config`, `ssh_info`) are a public interface: renaming or removing one is a breaking change for the repositories that call the action. |
| Cloud resource leaks | Anything created outside the Pulumi state, such as snapshot images taken through `openstacksdk` in `tools/`, has a deletion path. Snapshot images keep the `<product>-<snapshot>-` prefix that `delete-snapshot` finds them by. CI jobs that spawn a platform destroy it in a step that runs whatever the outcome. Retry loops do not `pulumi cancel` between attempts. |
| Network exposure | No `0.0.0.0/0` or widened `authorized_cidrs` default, no new public address on a node, no new open port by default. Security group and router changes keep each plane isolated as described in `DESIGN.md`. |
| Secrets and public content | The repository is public. No credentials, internal hostnames, private CIDRs or internal URLs in code, defaults, docs or workflow files. SSH private keys stay secret Pulumi outputs and never reach logs or step summaries. |
| GitHub workflows | Third-party actions and reusable workflows are pinned by commit SHA with a version comment. `permissions` are the minimum the job needs. `pull_request_target` never checks out and runs PR code with secrets. |
| Python | Code passes `ruff` with every rule enabled and is type annotated. Exceptions are caught by their specific type (`openstack.exceptions.SDKException`, not bare `except`). Pulumi `Output` values are combined with `apply`/`Output.all`/`Output.concat`, never formatted into plain strings. |
| Tests and docs | A behaviour change is covered by a check in `tests/` or an entry in the end to end matrix. Checks stay runnable against a platform spawned by hand. `DESIGN.md` and `docs/` follow behaviour changes. |
| Breaking changes | Anything that changes the action interface, the configuration keys, the stack outputs, the snapshot naming, or the S3 state path breaks callers in other repositories. The PR says so and the release notes carry it. |
