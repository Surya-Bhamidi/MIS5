# MIS5 research dashboard

The default view shows verified frozen AIT results: model comparison, campaign warnings, sensor-availability controls, 15-/30-minute horizons, archived forecast playback and presentation plots. Response recommendations use the research Decision Network's default assumed costs; they do not execute defenses.

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

Open http://127.0.0.1:5173. Requests to `/api` are proxied to port 8000. The default research view reads existing JSON/NPZ evidence under `experiments/`; raw datasets and model refitting are unnecessary. If needed, generate plot assets from the project root with `python Plots/create_mids_plots.py`.

**Earlier demo** opens the retained DARPA/synthetic interface. Its phase-classification outputs and SQLite experiment results are separate from the current AIT research scores.

Replay uses independent causal batches and local seeking. Scenario, mode, horizon
and simulation controls discard stale HTTP replies. Identical simulated actions
have identical loss curves; both series share a scale and use model units.
Cached legacy RQ reports can predate the simulation corrections and carry a
separate caveat. The API accepts local peers and approved local browser origins;
it does not provide production user authentication.

Checks: `npm run build`, `npm run lint`, and `python -m unittest discover -s backend/tests` from the project root. Offline replay inspects previously recorded results, not live deployment or independent generalization.
