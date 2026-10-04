"""Fetch public AIT-ADS inputs for an isolated research pilot."""
from pathlib import Path
import hashlib
import time
import zipfile
import requests

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "data" / "research" / "ait_ads"
FILES = {
    "labels.csv": "60ff33796c77fd2136c4d1a4bc841bd9",
    "ait_ads.zip": "43db6b1f0996e0024befd617706c50e9",
}


def fetch():
    DEST.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        path = DEST / name
        if path.exists():
            with path.open("rb") as existing:
                matches = hashlib.file_digest(existing, "md5").hexdigest() == expected
            if matches:
                print(f"Verified existing {name}", flush=True)
                continue
        url = f"https://zenodo.org/records/8263181/files/{name}?download=1"
        partial = path.with_suffix(path.suffix + ".partial")
        checksum = hashlib.md5()
        total = 0
        last = time.monotonic()
        with requests.get(url, stream=True, timeout=(20, 40)) as response:
            response.raise_for_status()
            with partial.open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    output.write(chunk)
                    checksum.update(chunk)
                    total += len(chunk)
                    if time.monotonic() - last > 5:
                        print(f"{name}: {total / 1e6:.1f} MB", flush=True)
                        last = time.monotonic()
        if checksum.hexdigest() != expected:
            raise ValueError(f"Checksum mismatch for {name}: {checksum.hexdigest()}")
        partial.replace(path)
        print(f"Downloaded and verified {name}: {total} bytes", flush=True)
    with zipfile.ZipFile(DEST / "ait_ads.zip") as archive:
        for member in archive.infolist():
            print(f"Archive member: {member.filename} ({member.file_size} bytes)", flush=True)
        member = next(m for m in archive.infolist() if m.filename.endswith("_wazuh.json"))
        with archive.open(member) as stream:
            print("JSON sample:", stream.read(6000).decode("utf-8", errors="replace"), flush=True)


if __name__ == "__main__":
    fetch()
