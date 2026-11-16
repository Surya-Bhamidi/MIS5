# MIS5 demonstration and research dashboard

The default interface is a presentation workspace with eight campaign replays,
interactive risk timelines, six-horizon forecasts, sensor switches, modeled
response comparisons, model results, downloadable figures and a presentation
guide. It reads bundled, real frozen evidence and **does not need the Python
backend, raw datasets or model training** to demonstrate the project.

For the quickest presentation, run from this folder:

```powershell
npm ci  # Only needed if dependencies are not installed
npm run dev
```

Open http://127.0.0.1:5173 and select **Presentation guide** for a walkthrough.
Use the expand button in the header to hide the sidebar for a presentation;
Escape restores it. Playback supports pause, reset, speed changes, a keyboard
accessible timeline and jumping to the first timely warning. Sensor switches
select archived experts; all sensors off means abstention. This is an archived
research demonstration, not a connection to live security sensors.

**Saved evidence** is selected by default. To read the local API instead, start
the backend below and change the header's evidence source to **Local Python
API**. API failures are shown explicitly; the interface does not silently
replace failed API evidence with a saved copy. **Research dashboard** opens the
retained detailed interface and requires the API.

**Export summary** downloads results for the current sensor/horizon selection
and the selected campaign. Comparison figures and the full-sensor CSV are fixed
published artifacts, labeled independently of the current filters.

To regenerate bundled evidence after an intentional research-artifact update,
run from the repository root:

```powershell
python backend/research/export_showcase.py
```

The exporter calls the same read-only research functions as the API, verifies
source checksums, and writes 135 JSON/plot/CSV assets plus their SHA-256 manifest
under `public/demo/`. It performs no fitting or tuning. Commit the generated
files with any intentional evidence changes. Browser delivery of these files
does not repeat the backend's source verification.

Build validation: `npm run build`. A browser smoke check covers playback,
sensor abstention, campaigns, exports, API recovery and responsive layouts.
From the repository root, with the frontend and API running and Python Playwright installed:

```powershell
python frontend/tests/showcase_smoke.py
# Or choose an installed Chromium browser, from the repository root:
python frontend/tests/showcase_smoke.py --browser 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
```

The browser check writes screenshots under ignored `reports/previews/`.

## Detailed research dashboard

The detailed research view shows verified frozen AIT results: model comparison, campaign warnings, sensor-availability controls, 15-/30-minute horizons, archived forecast playback and presentation plots. Response recommendations use the research Decision Network's default assumed costs; they do not execute defenses.

Run the backend from the project root:

The operational panel distinguishes the responsive live default from the optional
confirmed profile and shows the rejected validation candidate. It also reports
the latest local latency and paired inference comparison. These remain archived
comparisons; the page does not connect sensors or execute defensive actions.

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Then run the frontend from this folder:

```powershell
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Requests to `/api` are proxied to port 8000. The detailed research view reads existing JSON/NPZ evidence under `experiments/`; raw datasets and model refitting are unnecessary. If needed, generate plot assets from the project root with `python Plots/create_mids_plots.py`.

**Earlier demo** opens the retained DARPA/synthetic interface. Its phase-classification outputs and SQLite experiment results are separate from the current AIT research scores.

Replay uses independent causal batches and local seeking. Scenario, mode, horizon
and simulation controls discard stale HTTP replies. Identical simulated actions
have identical loss curves; both series share a scale and use model units.
Cached legacy RQ reports can predate the simulation corrections and carry a
separate caveat. The API accepts local peers and approved local browser origins;
it does not provide production user authentication.

Checks: `npm run build`, `npm run lint`, and `python -m unittest discover -s backend/tests` from the project root. Offline replay inspects previously recorded results, not live deployment or independent generalization.
