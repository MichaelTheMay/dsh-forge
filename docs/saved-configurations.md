# Saved Harness configurations

A saved configuration binds a stable local Harness version ID to a small launch
preset and, optionally, one locally trusted signed package. It never stores
credentials, arbitrary commands, source paths, package URLs, or unverified code.

Browse Packages, Plugins, or Forks and choose **Save configuration**. A package
with a locally configured signed recipe can be saved as a package-backed
configuration. A raw plugin or fork is saved as an inert draft because catalog
metadata is not executable trust.

The same workflow is available through the versioned CLI:

```bash
python3 -m dsh_forge configurations save \
  --name "AgentTeams builder" \
  --version version_REPLACE_ME \
  --package agent-teams-builder \
  --select package:catalog-package:agent-teams-builder \
  --profile web

python3 -m dsh_forge configurations list
python3 -m dsh_forge configurations run config_REPLACE_ME
```

`configs` is a short alias for `configurations`. Use `--json` for the stable
`dsh-forge.cli/v1` envelope.

## Run policy

- MCP-created configurations begin as drafts and require an explicit
  `configurations approve` action.
- Plugin or fork selections without a signed package remain non-runnable even
  after approval. Compose, sign, and configure one package recipe first.
- Package-backed configurations become runnable only when the exact package,
  saved version, tree, and profile match a successful sandbox-install receipt.
- Run clones the atomically promoted profile into a fresh cell. It requires the
  pinned Apptainer backend and has no host-process fallback.
- Removing a configuration changes only the schema-versioned registry under
  the Forge state directory; it never deletes Harness or package files.

The public schema is
`schemas/dsh-forge-configuration-v1.schema.json`. Registry writes use a
cross-process lock, private permissions, a fresh temporary file, `fsync`, and an
atomic replace.
