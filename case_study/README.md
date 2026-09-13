# SQCAD Case Study

Open the [interactive website](https://topps-2025.github.io/SQCAD/) or the
[English documentation in the repository](https://github.com/Topps-2025/SQCAD/blob/main/docs/docs_en/00_overview.md).
The GitHub repository hosts the source; GitHub Pages serves the interactive HTML.

- `index.html` is the browser replay and audit view.
- `app.js` contains the current inline story fixtures. The older local `data/replay.json` is not used by this page.
- `future-model.js` declares four three-task continuations, the hypothetical payoff triples, and the expectation calculation; none of its numbers are empirical paper results.
- `future-view.js` renders illustrated child branches, independent evidence routes, and the interactive horizon/policy/probability comparison. Selecting a qualified action does not overwrite the root choice.
- `godot/` is a separate Godot 4.x source prototype, not an embedded web export.
- Documentation links open the repository's English overview, method, or paper source. `docs/guide.html` only redirects older bookmarks to the repository; there is no separate browser technical guide to maintain.
- `assets/` contains generated illustrations for the flagship, finance, care, and software cases; exact evidence and labels remain HTML.

The replay is intentionally small and deterministic. It is an explanatory artifact, not a deployed system, a native reproduction of every named baseline, or a SOTA claim. No API keys are required at runtime.

Follow either root choice, expand A or B, and choose a child future. The bridge then opens Probe/Resolve/Defer as counterfactual alternatives. The final value landscape enumerates all four leaves of the finite teaching model; it does not claim to enumerate all real futures. Its evidence-aware policy is allowed to remove the score-fiber collision.

Run the model and asset checks with `node --test case_study/tests/future-model.test.cjs`.

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
