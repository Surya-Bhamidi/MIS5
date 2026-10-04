# Local research data

Raw datasets, downloaded logs, feature caches and the SQLite demonstration database are kept locally and excluded from this repository. The published experiment reports, score tables and frozen forecast archives remain under `experiments/`.

## AIT inputs for the current version

The current forecast uses [AIT-ADS](https://zenodo.org/records/8263181). Download and prepare it from the repository root:

```powershell
python backend/research/fetch_ait.py
python backend/research/evidence_pilot.py prepare
python backend/research/prepare_extended_data.py ait
```

The download script checks the original archive and labels against recorded publisher checksums. These commands create local inputs under `data/research/ait_ads/` and eight `ait_*_v2.npz` feature files under `data/research/extended/`. They prepare the inputs; they do not create fresh independent test campaigns or change the frozen research conclusions.

Once those inputs exist, run `python backend/research/verify_current_version.py` to verify the current preset, including a refit of one retained fold. Full historical endpoint/transfer audits additionally require their original evidence files.

## DARPA demonstration and supplementary experiments

The existing ingestion code expects these archives at the repository root:

```text
LLS_DDOS_1.0.tar.gz
LLS_DDOS_2.0.2.tar.gz
```

They come from the DARPA 2000 LLDOS evaluation datasets. Obtain the original archives from the dataset publisher, preserving those filenames. Run `python backend/run_ingestion.py` to create `data/cyber_prob.db` for the demonstration. Run `python backend/research/prepare_extended_data.py darpa` for the separate packet/count research inputs. No archives are bundled in this repository.

## Other evidence

The research reports identify [AIT Log Data Set v2](https://zenodo.org/records/5789064) endpoint evidence and [CAM-LDS](https://zenodo.org/records/18390561) external-transfer inputs. Acquisition and inspection scripts live under `backend/research/`; their manifests record downloaded members and verification scope. See the [publication validation report](../experiments/publication_validation/REPORT.md) for which endpoints were validated and which transfer outcomes are only proxies.

Dataset licensing and source provenance remain with the original publishers. Historical hash manifests include local inputs and intermediate caches; those entries cannot be verified from a source-only clone until the corresponding files are restored.
