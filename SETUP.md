# Automatic GitHub profile README

## One-time installation

1. Create or open a **public** GitHub repository named exactly like your GitHub username.
2. Put `README.md`, `profile.json`, `assets/`, `scripts/`, and `.github/workflows/refresh-profile.yml` in its default branch. Keep the folders in the same layout as this bundle.
3. Commit the files. The first push starts the refresh workflow.

The workflow detects the repository owner, so the artwork will use your actual username even if it differs from the sample screenshot. It runs daily at 06:17 UTC and can also be started from the repository's **Actions** tab. It commits updated files automatically.

## What updates

- GitHub bio, avatar, followers, public repository count, and stars
- Four most recently pushed public projects, excluding forks, archived repositories, and the profile repository
- Top four languages by code size across all public code repositories, excluding forks, archived repositories, and the profile repository
- Last 26 weeks of contributions, current and longest streaks, and contributions this year
- Recent public pushes, drawn as comets

`profile.json` is generated data. You do not need to edit it after installation. The workflow uses GitHub's built-in token, so public metrics require no extra secret.

If you want private contribution counts included, add an optional repository secret named `PROFILE_METRICS_TOKEN` with `read:user` access. GitHub's GraphQL documentation explains that scope requirement: https://docs.github.com/en/graphql/reference/users#object-contributionscollection

## Local check

```bash
python3 -m unittest discover -s tests -v
python3 scripts/generate.py
```

To fetch live data locally, set `GITHUB_TOKEN` in your shell and run `python3 scripts/sync_github.py`.
