# Godot companion

This is a Godot 4.x, renderer-compatible 2D companion for the SQCAD score-fiber replay. It visualizes one visible evidence state splitting into two possible futures. It intentionally avoids a room/world metaphor. The browser's `data/replay.json` is the canonical replay contract.

Open `project.godot` in Godot 4.x and run `Main.tscn`. Use Space to advance, Enter to reveal the continuations, and R to reset. The scene is self-contained so it can be tested without a local web server; when exported alongside the web artifact, keep the same event order and labels.

For a public HTML5 export, use a Godot 4.x web preset with the compatibility renderer. Do not embed API keys, hidden benchmark labels, local filesystem paths, or author metadata in the export. Keep the technical guide linked from the host page.
