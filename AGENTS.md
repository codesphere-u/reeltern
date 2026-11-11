# Working on Reeltern

Reeltern is a local Python video editor and stdio MCP server. This file guides coding assistants changing the repository. To operate the editor through MCP, read `docs/agent-workflow.md` instead.

## Start here

Read `README.md`, `docs/implementation.md` and the modules relevant to the change. `docs/roadmap.md` describes proposals, not implemented capabilities. `VALIDATION.md` records evidence and gaps. No Node/web service or hosted model is required for the core.

## Commands

- Install in an isolated environment: `python -m pip install -e '.[mcp]'`.
- Tests: `python -m unittest discover -s tests -v`.
- Synthetic demonstration: `python -m reeltern.cli demo --workspace demo-project`.
- Refresh tool schemas after interface changes: `python scripts/export_mcp_reference.py`.
- Package: `python -m pip wheel . --no-deps --wheel-dir dist`.

Use Python 3.12 for CI parity. Do not install large optional models to perform ordinary core checks.

## Engineering constraints

- Put editing behavior in the core; desktop, CLI and MCP wrappers must agree.
- Preserve original media and immutable plans. Add revisions instead of rewriting plan files.
- Source times and timeline times differ. Validate finite ranges and quantize output through existing plan construction.
- Preserve attached transcript IDs on revisions. Supplied text is not verified speech.
- Changes to rendered pixels/audio must invalidate affected cache keys.
- Use argument arrays for subprocesses; keep cancellation, timeouts and disk logs. MCP stdout contains protocol messages only.
- Keep media-root scoping and one-renderer ownership. Do not widen access as a workaround for a failing test.
- Model output is untrusted data. It cannot become shell commands, tool names, URLs or arbitrary timestamps.
- Test meaningful outputs for behavior changes. Synthetic fixtures belong in tests; private footage, credentials, model weights and working projects do not belong in commits.
- Keep capabilities, schemas, examples, changelog and docs consistent. State what was actually tested and what remains experimental.

Follow the user's requested scope. Do not add cloud services, hidden downloads, analytics or publishing steps as prerequisites for local editing.
