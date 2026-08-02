# Jenkins CI/CD boundary

Jenkins is a core **repository development and release workflow**, not an installed application feature.

## Repository-owned assets

- `Jenkinsfile` defines the maintained pipeline.
- `scripts/jenkins-local-job.sh` installs or updates the local Jenkins server job.
- `scripts/jenkins-local-job.xml` is the source-controlled job definition.

These files remain versioned, reviewed, and release-gated with the project. They may build wheels, run tests, validate source assets, and install a development-host profile.

## Distribution boundary

The Jenkins assets and `.github/workflows/` must not appear in:

- the installed Python wheel;
- installed executable/library paths;
- Linux, WSL2, or macOS runtime bundles.

They may appear in a full source checkout. Source distributions must not cause them to be installed as package data.

## Optional feature profiles

The default runtime install is the base CLI. Jenkins may request `--extras mcp` for a job that exercises the optional MCP feature. This is a CI profile decision and does not make MCP a base dependency.

## Verification

Release tests inspect wheel and runtime-bundle inventories and fail if repository-only Jenkins/GitHub workflow paths are present.
