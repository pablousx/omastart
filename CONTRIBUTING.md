# Contributing

Start with an existing issue, or open one to discuss substantial changes. Small fixes can go directly to a pull request.

1. Fork the repository and create a branch from the default branch.
2. Keep changes focused and follow the existing style.
3. Add or update tests for behavior changes and update relevant documentation.
4. Run the checks described in the README.
5. Open a pull request explaining the problem, the change, and how you verified it.

Do not include credentials, private data, or unrelated generated files. Follow the [code of conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

Maintainers use squash merging. A maintainer bypass exists for exceptional cases; normal changes should still use pull requests and passing checks. Contributions are provided under the repository's [license](LICENSE).

## Project checks

```bash
python3 -m unittest discover -v
```

Native QML and Omarchy checks require the desktop environment described in the README. Keep automated tests isolated from real user configuration. See [GitHub repository configuration](GITHUB_SETUP.md) for the shared configuration checks and settings.
