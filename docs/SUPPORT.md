# Support

`agent-workflow` is currently a pre-public-release project without a guaranteed support service level.

For trusted-collaborator use:

1. run `agent-workflow doctor` and retain its output;
2. capture the command, public error output, platform, Python, Git, and tmux versions;
3. identify the affected session or workflow without publishing private prompts or state artifacts;
4. reproduce with the smallest safe repository or prompt pack;
5. check [BACKLOG.md](BACKLOG.md), [Operations](OPERATIONS.md), and the [feature determinism/security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md).

Do not publish XDG state directories, prompts, source fragments, provider streams, credentials, or sealed evidence bundles without reviewing their contents.

A public issue tracker and monitored vulnerability-reporting channel must be established before the first supported public release. Security reports should follow [SECURITY.md](SECURITY.md).
