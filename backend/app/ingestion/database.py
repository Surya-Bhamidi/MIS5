import sqlite3
from contextlib import contextmanager
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from app.config import DB_PATH

logger = logging.getLogger(__name__)
EVENT_TABLES = frozenset({'events_lldos1','events_lldos2','events_synthetic'})

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events_lldos1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    timestamp_iso TEXT,
    src_ip TEXT,
    src_port TEXT,
    dst_ip TEXT,
    dst_port TEXT,
    service_name TEXT,
    alert_type TEXT,
    signature_category TEXT,
    port_class TEXT,
    sensor_source TEXT,
    session_cooccurred INTEGER,
    sensor_corroboration TEXT,
    true_phase_label INTEGER,
    source_file TEXT
);

CREATE INDEX IF NOT EXISTS idx_lldos1_ts ON events_lldos1 (timestamp);
CREATE INDEX IF NOT EXISTS idx_lldos1_phase ON events_lldos1 (true_phase_label);

CREATE TABLE IF NOT EXISTS events_lldos2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    timestamp_iso TEXT,
    src_ip TEXT,
    src_port TEXT,
    dst_ip TEXT,
    dst_port TEXT,
    service_name TEXT,
    alert_type TEXT,
    signature_category TEXT,
    port_class TEXT,
    sensor_source TEXT,
    session_cooccurred INTEGER,
    sensor_corroboration TEXT,
    true_phase_label INTEGER,
    source_file TEXT
);

CREATE INDEX IF NOT EXISTS idx_lldos2_ts ON events_lldos2 (timestamp);
CREATE INDEX IF NOT EXISTS idx_lldos2_phase ON events_lldos2 (true_phase_label);

CREATE TABLE IF NOT EXISTS events_synthetic (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    timestamp REAL,
    timestamp_iso TEXT,
    src_ip TEXT,
    src_port TEXT,
    dst_ip TEXT,
    dst_port TEXT,
    service_name TEXT,
    alert_type TEXT,
    signature_category TEXT,
    port_class TEXT,
    sensor_source TEXT,
    session_cooccurred INTEGER,
    sensor_corroboration TEXT,
    true_phase_label INTEGER,
    source_file TEXT
);

CREATE INDEX IF NOT EXISTS idx_syn_run ON events_synthetic (run_id, timestamp);

CREATE TABLE IF NOT EXISTS experiment_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rq_name TEXT UNIQUE,
    metrics_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

class Database:
    @staticmethod
    def validate_table(table_name):
        if table_name not in EVENT_TABLES:raise ValueError('Unknown event table')

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self):
        """Commit/rollback the transaction and always release the connection."""
        conn = self.get_connection()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def insert_events(self, table_name: str, events: List[Dict[str, Any]], run_id: Optional[str] = None):
        """Batch inserts normalized event dictionaries into specified table."""
        self.validate_table(table_name)
        if table_name=='events_synthetic' and (not isinstance(run_id,str) or not run_id.strip() or len(run_id)>128):
            raise ValueError('Synthetic writes require a nonempty run ID of at most 128 characters')
        if not events:
            if table_name=='events_synthetic':
                with self.connection() as conn:conn.execute('DELETE FROM events_synthetic WHERE run_id=?',(run_id,))
            return

        with self.connection() as conn:
            if run_id and table_name == "events_synthetic":
                conn.execute("DELETE FROM events_synthetic WHERE run_id = ?", (run_id,))
            else:
                conn.execute(f"DELETE FROM {table_name}")

            sql = f"""
            INSERT INTO {table_name} (
                timestamp, timestamp_iso, src_ip, src_port, dst_ip, dst_port,
                service_name, alert_type, signature_category, port_class,
                sensor_source, session_cooccurred, sensor_corroboration,
                true_phase_label, source_file
                {', run_id' if run_id and table_name == 'events_synthetic' else ''}
            ) VALUES (
                :timestamp, :timestamp_iso, :src_ip, :src_port, :dst_ip, :dst_port,
                :service_name, :alert_type, :signature_category, :port_class,
                :sensor_source, :session_cooccurred, :sensor_corroboration,
                :true_phase_label, :source_file
                {', :run_id' if run_id and table_name == 'events_synthetic' else ''}
            )
            """
            rows=[{**event,'run_id':run_id} for event in events] if table_name=='events_synthetic' else events
            conn.executemany(sql, rows)
            conn.commit()

    def get_events(
        self,
        table_name: str,
        limit: Optional[int] = None,
        offset: int = 0,
        run_id: Optional[str] = None,
        phase: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        self.validate_table(table_name)
        if limit is not None and (not isinstance(limit,int) or isinstance(limit,bool) or limit<0):raise ValueError('Invalid event limit')
        if not isinstance(offset,int) or isinstance(offset,bool) or offset<0:raise ValueError('Invalid event offset')
        with self.connection() as conn:
            query = f"SELECT * FROM {table_name} WHERE 1=1"
            params = []
            if run_id and table_name == "events_synthetic":
                query += " AND run_id = ?"
                params.append(run_id)
            if phase is not None:
                query += " AND true_phase_label = ?"
                params.append(phase)
            query += " ORDER BY timestamp ASC, id ASC"
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def get_event_count(self, table_name: str, run_id: Optional[str] = None) -> int:
        self.validate_table(table_name)
        with self.connection() as conn:
            query = f"SELECT COUNT(*) FROM {table_name}"
            params = []
            if run_id and table_name == "events_synthetic":
                query += " WHERE run_id = ?"
                params.append(run_id)
            cur = conn.execute(query, params)
            return cur.fetchone()[0]

    def save_experiment_result(self, rq_name: str, metrics: Dict[str, Any]):
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO experiment_results (rq_name, metrics_json) VALUES (?, ?) "
                "ON CONFLICT(rq_name) DO UPDATE SET metrics_json = excluded.metrics_json, created_at = CURRENT_TIMESTAMP",
                (rq_name, json.dumps(metrics, indent=2))
            )
            conn.commit()

    def get_experiment_result(self, rq_name: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute("SELECT metrics_json FROM experiment_results WHERE rq_name = ?", (rq_name,))
            row = cur.fetchone()
            if row:
                return json.loads(row["metrics_json"])
            return None

    def get_all_experiment_results(self) -> Dict[str, Any]:
        with self.connection() as conn:
            cur = conn.execute("SELECT rq_name, metrics_json FROM experiment_results")
            return {row["rq_name"]: json.loads(row["metrics_json"]) for row in cur.fetchall()}
