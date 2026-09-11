# Power-user plugin sets as discovery evidence

Public power-user repositories can reveal useful plugin combinations that do
not rank highly in catalogs. Treat this as an additional lead source, not a
trust source or permission to copy code.

## Additional evidence to collect

For an explicitly public repository and immutable commit, parse only declared
configuration and lock data: DSH profile patches, package manifests, lockfiles,
plugin enablement lists, and exact resolved versions/integrities. Record the
repository ID, commit, path, blob digest, observation time, and parser version.
Never collect committed credentials, local session logs, private configuration,
or inferred user identity.

Co-installation at a commit is evidence that a user configured two plugins
together. It is not proof that the combination installed successfully, ran at
the same time, remained compatible, or was secure. A candidate package should
therefore carry `metadata_only_unexecuted` provenance until reproducible static
inspection and sandbox tests exist.

## Ranking and product boundary

Rank observed sets using reproducible signals: number of independent public
repositories, recency, exact-pin coverage, license clarity, declared Harness
compatibility, dependency/conflict consistency, and security blast radius.
Stars remain display metadata. Deduplicate forks and copied lockfiles by content
digest so one template does not look like independent adoption.

The implemented pipeline first creates a metadata-only research proposal. A
curator must review source identity, permissions, licenses, and compatibility,
then sign the exact manifest. The front-page action verifies the recipe,
acquires matching bytes into quarantine, inspects the archive, builds without
network or lifecycle scripts, and runs smoke checks in Apptainer before atomic
promotion. See [Hidden-gem research and publication](../hidden-gem-pipeline.md).

Before redistributing a package recipe or artifact, verify license terms for
every component. A public commit or npm download does not automatically grant
the right to repackage or endorse it.
