# Releases and installation packages

Download assets from [GitHub Releases](https://github.com/codesphere-u/reeltern/releases). Version 0.3.2 is an early-preview release with Python installation bundles, a wheel and source distribution. It is not a standalone native executable, signed installer, or offline package.

## Choose a download

| Asset | Use it for | Requirements |
|---|---|---|
| `reeltern-0.3.2-windows-python.zip` | Windows installation with command/desktop launchers | Python 3.10–3.12 recommended; x64 release checks |
| `reeltern-0.3.2-macos-python.zip` | macOS installation with shell/desktop launchers | Python 3.10–3.12 recommended; Apple Silicon and Intel release checks |
| `reeltern-0.3.2-linux-python.zip` | Linux installation with a shell launcher | Python 3.10–3.12 recommended; x64 release checks; a desktop session and Tkinter for GUI |
| `reeltern-0.3.2-py3-none-any.whl` | Existing Python environments, CLI, MCP or embedding | Compatible PyAV and imageio-ffmpeg wheels/binaries for the platform |
| `reeltern-0.3.2.tar.gz` | Source development and rebuilding | Build dependencies and a supported Python environment |
| `SHA256SUMS.txt` | Detect a damaged or altered download | Compare the SHA-256 hash with the release's checksum list |

The three installation ZIPs contain the same pure-Python Reeltern wheel with OS-specific launchers. They install dependencies from the user's configured Python package index into a private `.venv` inside the extracted folder. They do not contain a Python runtime, downloaded model weights, or third-party dependency binaries. Installation requires internet access and does not install packages globally.

## Installation bundles

1. Extract the entire ZIP into a writable folder, then open a terminal there.
2. Install using your chosen Python:

```sh
# macOS / Linux (Python 3.12 recommended)
python3 install.py
```

```powershell
# Windows
py -3.12 install.py
```

3. Try a complete synthetic edit:

```sh
# macOS / Linux
sh reeltern.sh demo --workspace demo-project
sh reeltern.sh gui
```

```powershell
# Windows
.\reeltern.cmd demo --workspace demo-project
.\reeltern.cmd gui
```

macOS includes `Launch.command`, and Windows includes `Launch.cmd`, for desktop launch after installation. CLI and MCP work without Tkinter or a display. Linux GUI installations may need `python3-tk`; environment creation may need `python3-venv`. Install a Python distribution with Tk support for desktop use on macOS/Windows.

Downloaded scripts are unsigned. Inspect the files and use the terminal commands above if your OS asks you to review them. Do not disable system security protections to run the package. Move the extracted folder before installation, not after: virtual environments and generated MCP settings use absolute paths.

## Existing Python environment

From the directory containing the downloaded wheel:

```sh
python -m venv .venv
# Activate it, or use its Python executable directly.
python -m pip install './reeltern-0.3.2-py3-none-any.whl[mcp]'
python -m reeltern.cli demo --workspace demo-project
```

On Windows, use `.\.venv\Scripts\python.exe`; on Unix, use `.venv/bin/python`. Installing without `[mcp]` provides the core CLI/desktop dependencies; use the MCP extra to connect assistants. The installation bundles include that extra automatically. There is no PyPI or GitHub Packages registry publication in this release; GitHub release assets are the distribution channel.

## Supported and tested environments

The release workflow targets the following combinations before publication:

| Runner / architecture | Python | Checks |
|---|---|---|
| Ubuntu 22.04 / x86-64 | 3.10, 3.11, 3.12 | Core tests, clean bundle install, real demo render, cache reuse, MCP handshake |
| Windows Server 2022 / x86-64 | 3.10, 3.11, 3.12 | Same checks, including Windows command launcher |
| macOS 15 / Apple Silicon | 3.10, 3.11, 3.12 | Same checks, including shell launcher |
| macOS 15 / Intel | 3.10, 3.11, 3.12 | Same checks, including shell launcher |

This is runner-based evidence, not an exhaustive certification of every desktop OS release. Windows 10/11 and other Linux distributions may work when dependencies are available, but are not separately covered by these runners. Python 3.13+, Linux ARM, Windows ARM, Alpine/musl, and fully offline installation are not part of this release's tested matrix. The package declares Python 3.10+; newer interpreters are best-effort until tested. Desktop visual behavior is not covered by headless release checks.

Containers, WSL and SSH environments can use the wheel/CLI/MCP when a compatible Python and dependencies are available. They need their own server-visible paths; no dedicated container image or hosted HTTP service is published. Optional GPU/research adapters and Ollama models have separate compatibility requirements and are not validated by these package checks.

## Check a download

```sh
# Linux
sha256sum --check SHA256SUMS.txt
# macOS
shasum -a 256 reeltern-0.3.2-macos-python.zip
```

```powershell
Get-FileHash .\reeltern-0.3.2-windows-python.zip -Algorithm SHA256
```

Compare the reported digest with the corresponding line in `SHA256SUMS.txt`. To use the Linux all-files check, download all files named in the list; otherwise check the asset you downloaded individually. Checksums detect corruption; they are not a code-signing identity or independent trust guarantee.

## For maintainers

`release/version.txt` must match `pyproject.toml`. Changes to release metadata, packaging scripts or the release workflow on `main` start the workflow; manual dispatch is also available. It builds wheel/source/OS bundles, verifies the 12 combinations, then creates a draft GitHub prerelease, uploads assets with checksums, and publishes only after verification succeeds. Existing releases are not overwritten; use a new version for another publication.

The workflow uses the repository-scoped Actions token only in the publication job. It does not require a personal token or package-registry credential. Each release tag targets the exact tested commit. The bundled source remains available in the same release and repository. See [implementation](implementation.md) for development commands and [validation](../VALIDATION.md) for known limitations.
