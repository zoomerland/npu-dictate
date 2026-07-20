# Agent Guidelines

## Branching Workflow

Use a three-layer branching model for product work:

1. `main` is the stable release branch.
   Do not commit feature work directly to `main`.

2. `features/next` is the integration branch for the next batch of product changes.
   Feature branches are merged here first, tested together, and only then considered for release.

3. Each individual feature gets its own short-lived branch from `features/next`.
   For Codex-created branches, use the `codex/<feature-name>` prefix unless the user asks for another name.

Normal flow:

1. Start from `features/next`.
2. Create a feature branch for one bounded feature or fix.
3. Commit and validate the feature on that branch.
4. Merge the feature branch back into `features/next` after review/testing.
5. When the whole feature batch is ready, merge `features/next` into `main` for the next release.

Rules:

- Do not push, merge into `main`, tag, or create a release unless the user explicitly asks.
- Keep unrelated local files and user changes out of feature commits.
- If a feature branch was accidentally started from `main` while `features/next` is equivalent to `main`, it can remain as-is, but future feature branches should start from `features/next`.
- If `features/next` has moved ahead of `main`, rebase or recreate accidental `main`-based feature branches onto `features/next` before integration.
