import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime

class VehicleDatabase:
    """Local SQLite database for homelab vehicle leads."""
    
    def __init__(self, db_path: str = "platehound_leads.db"):
        self.db_path = db_path
        self._init_db()
        
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'FL',
                    make TEXT,
                    model TEXT,
                    year INTEGER,
                    body_class TEXT,
                    engine_info TEXT,
                    confidence REAL DEFAULT 1.0,
                    source TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(plate, state)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plate ON vehicle_leads(plate)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_make_model ON vehicle_leads(make, model)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_year ON vehicle_leads(year)")
            conn.commit()

    def upsert_lead(self, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO vehicle_leads (plate, state, make, model, year, body_class, engine_info, confidence, source, notes, updated_at)
            VALUES (:plate, :state, :make, :model, :year, :body_class, :engine_info, :confidence, :source, :notes, CURRENT_TIMESTAMP)
            ON CONFLICT(plate, state) DO UPDATE SET
                make=COALESCE(excluded.make, vehicle_leads.make),
                model=COALESCE(excluded.model, vehicle_leads.model),
                year=COALESCE(excluded.year, vehicle_leads.year),
                body_class=COALESCE(excluded.body_class, vehicle_leads.body_class),
                engine_info=COALESCE(excluded.engine_info, vehicle_leads.engine_info),
                confidence=MAX(vehicle_leads.confidence, excluded.confidence),
                notes=COALESCE(excluded.notes, vehicle_leads.notes),
                updated_at=CURRENT_TIMESTAMP
        """
        params = {
            "plate": data.get("plate", "").upper().strip(),
            "state": data.get("state", "FL").upper().strip(),
            "make": data.get("make"),
            "model": data.get("model"),
            "year": data.get("year"),
            "body_class": data.get("body_class"),
            "engine_info": data.get("engine_info"),
            "confidence": data.get("confidence", 1.0),
            "source": data.get("source", "alpr_lookup"),
            "notes": data.get("notes", "")
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def search_leads(self, query: Optional[str] = None, make: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM vehicle_leads WHERE 1=1"
        params = []
        if query:
            sql += " AND (plate LIKE ? OR make LIKE ? OR model LIKE ?)"
            val = f"%{query}%"
            params.extend([val, val, val])
        if make:
            sql += " AND LOWER(make) = LOWER(?)"
            params.append(make)
        if year:
            sql += " AND year = ?"
            params.append(year)
            
        sql += " ORDER BY created_at DESC"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vehicle_leads")
            return cursor.fetchone()[0]
