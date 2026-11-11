# Contributing

Reeltern is an early open-source project. Help improve concrete editing outcomes rather than adding unsupported capability claims.

Install `.[mcp]` in a virtual environment and run `python -m unittest discover -s tests -v`. Tests synthesize small media files, so no copyrighted fixtures or downloaded model weights are required.

A change should preserve original files, create reviewable decisions, validate inputs, expose errors and include a meaningful real-media test when it changes rendering. Keep MCP stdout clean. Document audio/timing/color behavior and whether a feature is tested, optional or experimental. Never include private footage, credentials, local workspaces or model weights in a pull request.

Priority contributions:

1. Tests with variable frame rates, rotated phone clips, offset audio and longer recordings.
2. Preview playback and waveform selection inside the desktop UI.
3. Word-level alignment, built-in transcription and evaluations of context-preserving editorial selections.
4. Scene-aware interpolation and temporally consistent background processing.
5. Cross-platform installers, cache quotas and broader process-crash recovery tests.
6. A reproducible benchmark corpus and measured comparisons before performance claims.

Licensing: original contributions are GPL-3.0-or-later. Preserve upstream notices and check weight/binary redistribution terms separately. Report failures with sanitized logs, tool versions and a minimal reproducible sample that you have permission to share.
