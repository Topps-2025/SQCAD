# SQCAD Case Study

Open the [interactive website](https://topps-2025.github.io/SQCAD/) or the
[English technical guide](https://topps-2025.github.io/SQCAD/case_study/docs/guide.html).
The GitHub repository hosts the source; GitHub Pages serves the interactive HTML.

- `index.html` is the browser replay and audit view.
- `app.js` contains the current inline story fixtures. The older local `data/replay.json` is not used by this page.
- `godot/` is a separate Godot 4.x source prototype, not an embedded web export.
- `docs/guide.html` is the browser technical guide with Letta ADE-style navigation and state inspection; `docs/TECHNICAL_GUIDE.md` remains the source narrative.
- `assets/` contains generated illustrations; exact evidence and labels remain HTML.

The replay is intentionally small and deterministic. It is an explanatory artifact, not a deployed system, a native reproduction of every named baseline, or a SOTA claim. No API keys are required at runtime.

## Run locally

Double-click the repository's `index.html` to enter the case study, or open
`case_study/index.html` directly. The script has no module imports or fetch
dependency. For an HTTP preview, run from the repository root:

```powershell
python -m http.server 4173
```

Open `http://localhost:4173/`. The root HTML forwards to the case study.

## Automatic publishing

`.github/workflows/pages.yml` deploys with GitHub's official Pages actions when
site files change on `main`, or when manually run from the Actions tab. Pages
must use **GitHub Actions** as its build source in repository Settings → Pages.

The upload uses an explicit list of public HTML, CSS, JavaScript, and WebP
assets. It excludes research data, evaluator files, art-generation records,
local credentials, and the Godot source project. Publishing does not need an
image-generation API key or a personal token stored in the repository.

The futures are hidden by the interface before the choice; the static
JavaScript source contains all story fixtures and is not a secure evaluator.

## Godot companion

Open `case_study/godot/project.godot` in Godot 4.x and run the project. Space advances, Enter reveals the continuations, and R resets. For a web export, configure an HTML5/Web preset and keep the browser replay as the canonical evidence surface.
