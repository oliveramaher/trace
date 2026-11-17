# Trace stream prototype

Run `python3 stream.py --app Finder --interval 2` with `agent-desktop` installed and available on PATH. Repeat `--app` to observe more apps. Stop with Ctrl-C. Each line on standard output is a JSON object containing a UTC timestamp, app name, and the snapshot response or an error. Redirect output to a file only if you want to retain it.

This polls selected apps in sequence, rather than recording every interaction. Short-lived changes between snapshots can be missed; slow or unresponsive apps delay the next round. For multiple windows, run `agent-desktop list-windows --app "Google Chrome"` and pass `--window-id ID` to the stream command. A snapshot can fail when an app lacks accessibility support. Accessibility permission is required. Snapshot content may include private information: output is not redacted. The prototype does not upload data or start automatically.

The upstream snapshot and platform adapter code are useful for observation. Interaction commands, sandbox execution, MCP, and screenshot capture are not required for this polling prototype. Keep them for now: removing them would require separating shared dependencies and deciding whether future playback or assistant control is in scope.
