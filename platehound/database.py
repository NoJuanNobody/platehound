import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime

class VehicleDatabase:
    """Local SQLite database for homelab vehicle leads with ALPR sightings & outreach enrichment."""
    
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
            # 1. Base table creation (with all modern columns)
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
                    vin_masked TEXT,
                    drive_type TEXT,
                    fuel_type TEXT,
                    lead_segment TEXT,
                    outreach_pitch TEXT,
                    image_path TEXT,
                    sightings_count INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 1.0,
                    source TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(plate, state)
                )
            """)

            # 2. Backward compatibility & schema migration for existing databases
            cursor.execute("PRAGMA table_info(vehicle_leads)")
            existing_columns = {row["name"] for row in cursor.fetchall()}
            
            migration_columns = [
                ("vin_masked", "TEXT"),
                ("drive_type", "TEXT"),
                ("fuel_type", "TEXT"),
                ("lead_segment", "TEXT"),
                ("outreach_pitch", "TEXT"),
                ("image_path", "TEXT"),
                ("sightings_count", "INTEGER DEFAULT 1"),
            ]
            
            for col_name, col_type in migration_columns:
                if col_name not in existing_columns:
                    cursor.execute(f"ALTER TABLE vehicle_leads ADD COLUMN {col_name} {col_type}")

            # Ensure any pre-existing records have sightings_count initialized
            cursor.execute("UPDATE vehicle_leads SET sightings_count = 1 WHERE sightings_count IS NULL")

            # 3. Indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plate ON vehicle_leads(plate)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_make_model ON vehicle_leads(make, model)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_year ON vehicle_leads(year)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_segment ON vehicle_leads(lead_segment)")
            conn.commit()

    def upsert_lead(self, data: Dict[str, Any]) -> int:
        """
        Inserts a new vehicle lead or updates an existing lead on (plate, state).
        When updating:
          - Sightings count is incremented by 1
          - Metadata and enriched specs are updated
          - Updated timestamp is refreshed
        """
        query = """
            INSERT INTO vehicle_leads (
                plate, state, make, model, year, body_class, engine_info,
                vin_masked, drive_type, fuel_type, lead_segment, outreach_pitch,
                image_path, sightings_count, confidence, source, notes, updated_at
            )
            VALUES (
                :plate, :state, :make, :model, :year, :body_class, :engine_info,
                :vin_masked, :drive_type, :fuel_type, :lead_segment, :outreach_pitch,
                :image_path, :sightings_count, :confidence, :source, :notes, CURRENT_TIMESTAMP
            )
            ON CONFLICT(plate, state) DO UPDATE SET
                make=COALESCE(excluded.make, vehicle_leads.make),
                model=COALESCE(excluded.model, vehicle_leads.model),
                year=COALESCE(excluded.year, vehicle_leads.year),
                body_class=COALESCE(excluded.body_class, vehicle_leads.body_class),
                engine_info=COALESCE(excluded.engine_info, vehicle_leads.engine_info),
                vin_masked=COALESCE(excluded.vin_masked, vehicle_leads.vin_masked),
                drive_type=COALESCE(excluded.drive_type, vehicle_leads.drive_type),
                fuel_type=COALESCE(excluded.fuel_type, vehicle_leads.fuel_type),
                lead_segment=COALESCE(excluded.lead_segment, vehicle_leads.lead_segment),
                outreach_pitch=COALESCE(excluded.outreach_pitch, vehicle_leads.outreach_pitch),
                image_path=COALESCE(excluded.image_path, vehicle_leads.image_path),
                sightings_count=COALESCE(vehicle_leads.sightings_count, 1) + 1,
                confidence=MAX(COALESCE(vehicle_leads.confidence, 0.0), excluded.confidence),
                source=COALESCE(excluded.source, vehicle_leads.source),
                notes=CASE
                    WHEN excluded.notes IS NOT NULL AND excluded.notes != ''
                    THEN excluded.notes
                    ELSE vehicle_leads.notes
                END,
                updated_at=CURRENT_TIMESTAMP
            RETURNING id
        """
        params = {
            "plate": str(data.get("plate", "")).upper().strip(),
            "state": str(data.get("state", "FL")).upper().strip(),
            "make": data.get("make"),
            "model": data.get("model"),
            "year": data.get("year"),
            "body_class": data.get("body_class"),
            "engine_info": data.get("engine_info"),
            "vin_masked": data.get("vin_masked"),
            "drive_type": data.get("drive_type"),
            "fuel_type": data.get("fuel_type"),
            "lead_segment": data.get("lead_segment"),
            "outreach_pitch": data.get("outreach_pitch"),
            "image_path": data.get("image_path"),
            "sightings_count": data.get("sightings_count", 1),
            "confidence": float(data.get("confidence", 1.0)),
            "source": data.get("source", "alpr_lookup"),
            "notes": data.get("notes", "")
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.commit()
            return row["id"] if row else cursor.lastrowid

    def get_lead(self, plate: str, state: str = "FL") -> Optional[Dict[str, Any]]:
        """Retrieve a single lead by plate and state."""
        sql = "SELECT * FROM vehicle_leads WHERE plate = ? AND state = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (plate.upper().strip(), state.upper().strip()))
            row = cursor.fetchone()
            return dict(row) if row else None

    def search_leads(
        self,
        query: Optional[str] = None,
        make: Optional[str] = None,
        year: Optional[int] = None,
        min_year: Optional[int] = None,
        segment: Optional[str] = None,
        body_class: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search and filter vehicle leads by multiple optional criteria.
        """
        sql = "SELECT * FROM vehicle_leads WHERE 1=1"
        params: List[Any] = []

        if query:
            sql += " AND (plate LIKE ? OR make LIKE ? OR model LIKE ? OR notes LIKE ? OR lead_segment LIKE ?)"
            val = f"%{query}%"
            params.extend([val, val, val, val, val])

        if make:
            sql += " AND LOWER(make) = LOWER(?)"
            params.append(make)

        if year is not None:
            sql += " AND year = ?"
            params.append(year)

        if min_year is not None:
            sql += " AND year >= ?"
            params.append(min_year)

        if segment:
            sql += " AND LOWER(lead_segment) LIKE LOWER(?)"
            params.append(f"%{segment}%")

        if body_class:
            sql += " AND LOWER(body_class) LIKE LOWER(?)"
            params.append(f"%{body_class}%")
            
        sql += " ORDER BY updated_at DESC, id DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns homelab database analytics:
        - total leads
        - total sightings count
        - average vehicle year
        - breakdown by make
        - breakdown by lead_segment
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(sightings_count), 0), AVG(year) FROM vehicle_leads")
            row = cursor.fetchone()
            total_leads = row[0] or 0
            total_sightings = row[1] or 0
            avg_year = round(row[2], 1) if row[2] is not None else None

            cursor.execute("""
                SELECT COALESCE(make, 'UNKNOWN') AS m, COUNT(*) AS cnt
                FROM vehicle_leads
                GROUP BY m
                ORDER BY cnt DESC
            """)
            by_make = {r["m"]: r["cnt"] for r in cursor.fetchall()}

            cursor.execute("""
                SELECT COALESCE(lead_segment, 'Unsegmented') AS s, COUNT(*) AS cnt
                FROM vehicle_leads
                GROUP BY s
                ORDER BY cnt DESC
            """)
            by_lead_segment = {r["s"]: r["cnt"] for r in cursor.fetchall()}

            return {
                "total_leads": total_leads,
                "total_sightings": total_sightings,
                "average_year": avg_year,
                "avg_year": avg_year,
                "by_make": by_make,
                "make_breakdown": by_make,
                "by_lead_segment": by_lead_segment,
                "lead_segment_breakdown": by_lead_segment
            }

    def count(self) -> int:
        """Returns total leads count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vehicle_leads")
            return cursor.fetchone()[0]

    def delete_lead(self, plate: str, state: str = "FL") -> bool:
        """Delete a lead record by plate and state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vehicle_leads WHERE plate = ? AND state = ?", (plate.upper().strip(), state.upper().strip()))
            conn.commit()
            return cursor.rowcount > 0
