# SQCAD Case Study

This directory contains the English interactive case-study artifact for SQCAD.

- `index.html` is the browser replay and audit view.
- `data/replay.json` is the shared deterministic replay contract.
- `godot/` is a Godot 4.x 2D companion view that reads the same contract.
- `docs/guide.html` is the browser technical guide with Letta ADE-style navigation and state inspection; `docs/TECHNICAL_GUIDE.md` remains the source narrative.
- `assets/` contains earlier optional visual assets; the current flagship replay uses code-rendered evidence and branch diagrams so the research claim remains inspectable.

The replay is intentionally small and deterministic. It is an explanatory artifact, not a deployed system, a native reproduction of every named baseline, or a SOTA claim. No API keys are required at runtime.

## Run locally

From the repository root:

```powershell
python -m http.server 4173 --directory case_study
```

Open `http://localhost:4173/`. The page must be served over HTTP because the replay data is loaded as a module/fetch resource.

## Godot companion

Open `case_study/godot/project.godot` in Godot 4.x and run the project. Space advances, Enter reveals the continuations, and R resets. For a web export, configure an HTML5/Web preset and keep the browser replay as the canonical evidence surface.
