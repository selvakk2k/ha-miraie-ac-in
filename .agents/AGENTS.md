# Custom Agent Rules

## GitHub CLI Tag and Release Management
- **Tag & Release**: Use the GitHub CLI (`gh release create <tag> --title "<tag>" --notes "<body_text>"`) or standard git commands (`git tag <tag> && git push origin <tag>`) to create tags and releases. If `gh` CLI is unavailable, retrieve the GitHub personal access token securely from `~/.git-credentials` (stored via local keyring/credential helper) and call the GitHub REST API (`POST /repos/{owner}/{repo}/releases`) to publish the release. Never store or embed personal access tokens in `.git/config` or remote URLs.

## Release Lifecycle & Pre-release Tagging Logic
- **Brand New Feature**: Create a pre-release tagged with `alpha` (e.g. `v1.4.0-alpha.1`).
- **Improving / Iterating Existing Feature**: Create a pre-release tagged with `beta` (e.g. `v1.4.0-beta.1`).
- **Minor Fixes / Explicit User Request**: Only then create a full release (e.g. `v1.3.22`).
- **Local Testing Recommendation**: If rapid iteration is beneficial, suggest to the user to test locally first before creating any tag or release.

## GitHub Release Notes Format
- **Format**: When publishing releases on GitHub, the release description (`body`) must use the standard release notes format:
  - Uses `## What's Changed` as the primary section header.
  - Lists changed items using bullet points.
  - Starts each bullet point with a bold term describing the feature/fix (e.g. `**Feature Name**: Description...`).
  - Codes/symbols should be highlighted in backticks (e.g. `__del__`, `close()`).

## Explain Before Code Changes
- **Rule**: Always explain clearly to the user what changes are being made and why **before** editing code or modifying files.
