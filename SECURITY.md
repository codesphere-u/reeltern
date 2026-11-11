# Security and privacy

Reeltern is local software, not a security sandbox. Use a workspace you control and media you trust. Keep Python, FFmpeg and optional model engines updated.

MCP imports are restricted to the configured media root. Paths are resolved before checking boundaries, including symlinks. The MCP interface does not expose arbitrary shell commands, output paths, HTML rendering or model-server addresses. The optional editorial agent is enabled at server startup and uses an HTTP loopback Ollama endpoint with proxies and redirects disabled. It rejects cloud-labeled model names, but your local model-service configuration ultimately controls how inference is handled; an alias or modified local service is not a trusted isolation boundary.

Transcripts are untrusted evidence. Model output is limited to known cue IDs and a duration budget. Invalid outputs get one repair attempt, then fail. These controls prevent the model from directly selecting arbitrary file paths or operations; they do not guarantee that selected quotes preserve meaning. Review context. The agent creates drafts, never automatically publishes or executes generated code.

Original media and transcripts remain in the workspace. MCP clients can see returned paths, quotes and metadata. Agent decision receipts may contain the editing brief and selected text. Do not share the workspace or logs without reviewing them. Captions may disclose transcript content even when a player hides its subtitle track.

To report a vulnerability, use GitHub private vulnerability reporting if enabled. Otherwise open a non-sensitive issue requesting a private contact channel. Do not post credentials, personal media or exploit details that expose another user's data in public issues. No response-time SLA is currently offered.
