---
name: qgit
description: |
  Stage all changes, create a Conventional Commits formatted commit, and push to remote.
  Enforces commit message conventions and branch naming rules. Replaces the QGIT shortcut.
user-invocable: true
---

# Git Commit and Push

Stage all changes, create a commit with a proper message, and push to the remote.

## Steps

1. **Stage** — Run `git add -A` to stage all changes
2. **Compose commit message** — Follow the format below
3. **Commit** — Create the commit
4. **Push** — Push to the remote tracking branch

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature (MINOR in SemVer) |
| `fix` | Bug fix (PATCH in SemVer) |
| `build` | Build system or external dependencies |
| `chore` | Maintenance tasks |
| `ci` | CI/CD configuration |
| `docs` | Documentation only |
| `style` | Formatting, whitespace (no logic change) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |

### Breaking Changes

A commit with footer `BREAKING CHANGE:` or `!` after the type/scope introduces a breaking API change (MAJOR in SemVer). A BREAKING CHANGE can be part of commits of any type.

## Rules

- MUST use Conventional Commits format
- MUST NOT refer to Claude or Anthropic in the commit message
- SHOULD keep the description line under 72 characters
- SHOULD use imperative mood ("add feature" not "added feature")
- Footers other than `BREAKING CHANGE:` may be provided following git trailer format
