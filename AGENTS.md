# computer-ctrl development

Read [README.md](README.md), [docs/development.md](docs/development.md) and the
relevant provider/setup guide before changing code. `contract/tools.json` defines
tool names, argument schemas and conventions; verify implementation as well.

- Treat desktop control, capture, process management and provider queries as live
  effects requiring explicit target/task authorization.
- Inspect imports and fixtures before running tests. Offline checks must deny
  network, subprocess and native access and use private fixture roots.
- Preserve host/isolated selection, generation checks, stale-frame refusal and
  unsupported-operation refusal. Never fall back from an isolated target to host.
- Keep credentials, captured content, machine configuration and session/eval
  records out of commits. Use synthetic fixtures with reserved-domain examples.
- Changes to native behavior need separately authorized native acceptance;
  static checks and mocked tests don't establish native behavior.
