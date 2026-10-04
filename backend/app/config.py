import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
DATA_DIR = BASE_DIR / "data"
EXPERIMENTS_DIR = BASE_DIR / "experiments"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

LLDOS_1_TAR = BASE_DIR / "LLS_DDOS_1.0.tar.gz"
LLDOS_2_TAR = BASE_DIR / "LLS_DDOS_2.0.2.tar.gz"
DB_PATH = DATA_DIR / "cyber_prob.db"

# 6 Threat States (Benign + 5 Kill-chain phases)
THREAT_STATES = [
    "Benign",
    "Recon",
    "Discovery",
    "Compromise",
    "PrivEsc",
    "ActiveAttack",
]

PHASE_LABELS = {
    0: "Benign (No Attack)",
    1: "Phase 1: IPsweep / Recon",
    2: "Phase 2: Sadmind Ping / Discovery",
    3: "Phase 3: Sadmind Breakin / Compromise",
    4: "Phase 4: Trojan mstream Install / PrivEsc",
    5: "Phase 5: DDoS Launch / Active Attack",
}

# Defensive Response Actions
DEFENSIVE_ACTIONS = [
    "Monitor",
    "Restrict",
    "Block",
    "Isolate",
]

# Utility Matrix: U(State, Action)
# Rows = States (0..5), Cols = Actions (Monitor, Restrict, Block, Isolate)
# Calibrated to DARPA 2000 LLDOS operational tradeoffs:
# - Monitor: 0 impact on benign, but severe catastrophic penalty if Phase 4 or 5 unchecked.
# - Restrict: mild friction, effective early mitigation against ping/sweep, negligible false-pos cost.
# - Block: drops attacker IP; beneficial in Phase 3/4, medium false-alarm cost if benign.
# - Isolate: quarantines victim host; highly destructive if applied false-positively (-120),
#   but prevents zombie botnet coordination and master host takeover (+140 in Phase 4/5).
UTILITY_MATRIX = {
    "Benign": {
        "Monitor": 10.0,
        "Restrict": -15.0,
        "Block": -45.0,
        "Isolate": -120.0,
    },
    "Recon": {
        "Monitor": 15.0,     # Observe scan signatures without revealing presence
        "Restrict": 5.0,     # Rate limit scanning
        "Block": -10.0,      # Premature block alerts attacker
        "Isolate": -90.0,    # Gross overreaction
    },
    "Discovery": {
        "Monitor": 0.0,
        "Restrict": 30.0,    # Throttle RPC queries to sadmind daemon
        "Block": 15.0,
        "Isolate": -50.0,
    },
    "Compromise": {
        "Monitor": -60.0,    # Attacker gaining root access
        "Restrict": 20.0,
        "Block": 80.0,       # Sever active exploit connection
        "Isolate": 50.0,
    },
    "PrivEsc": {
        "Monitor": -250.0,   # Trojan mstream deployment in progress!
        "Restrict": -50.0,   # Insufficient to stop persistence
        "Block": 45.0,
        "Isolate": 95.0,     # Quarantine host before it commands DDoS
    },
    "ActiveAttack": {
        "Monitor": -1000.0,  # Unmitigated catastrophic network outage
        "Restrict": -200.0,  # Overwhelmed by flood volume
        "Block": 60.0,       # Block flood sources
        "Isolate": 130.0,    # Sever mstream master host to stop orchestration
    },
}

# Signatures / Port classifications
SIGNATURE_CATEGORIES = [
    "ICMP_SWEEP",
    "RPC_DISCOVERY",
    "EXPLOIT_PAYLOAD",
    "REMOTE_SHELL",
    "DDOS_FLOOD",
    "BENIGN_ROUTINE",
]

TARGET_DIVERSITY = ["SINGLE_HOST", "MULTI_HOST"]
PORT_CLASSES = ["STANDARD", "RPC_HIGH", "FLOOD_EPHEMERAL"]
SENSOR_CORROBORATION = ["SINGLE_SENSOR", "DUAL_SENSOR"]
ALERT_RATES = ["LOW", "MEDIUM", "HIGH"]
