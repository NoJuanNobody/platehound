import unittest
import os
import tempfile
import csv
import json
import sqlite3
from typing import Dict, Any

from platehound.detector import FloridaPlateDetector
from platehound.lookup import VehicleLookupService
from platehound.database import VehicleDatabase
from platehound.exporter import export_csv, export_json, export_html_dashboard
from platehound.cli import enrich_lead_metadata


class TestPlateDetector(unittest.TestCase):
    """Tests for FloridaPlateDetector normalization, OCR cleanup, and FL schemas."""

    def setUp(self):
        self.detector = FloridaPlateDetector()

    def test_clean_plate_string(self):
        # Prefixes stripped
        self.assertEqual(self.detector.clean_plate_string("FL-76BCDE"), "76BCDE")
        self.assertEqual(self.detector.clean_plate_string("FL 76BCDE"), "76BCDE")
        self.assertEqual(self.detector.clean_plate_string("FLORIDA ABC123"), "ABC123")
        self.assertEqual(self.detector.clean_plate_string("  XYZ-789  "), "XYZ789")

    def test_flfast_vanity_plate_preservation(self):
        """
        Verify FLFAST vanity plate is preserved and not erroneously stripped
        as a Florida state prefix ('FL' -> 'FAST').
        """
        cleaned = self.detector.clean_plate_string("FLFAST")
        self.assertEqual(cleaned, "FLFAST", "Vanity plate FLFAST must not be stripped to FAST")

        # Also verify with spaces/lowercase
        self.assertEqual(self.detector.clean_plate_string("flfast"), "FLFAST")

    def test_validate_florida_plate(self):
        valid_plates = ["76BCDE", "ABC123", "XYZ789", "FLFAST", "SUNSHN", "MIA305", "GATOR1", "305EV1"]
        for p in valid_plates:
            is_valid, conf = self.detector.validate_florida_plate(p)
            self.assertTrue(is_valid, f"Plate {p} should be valid Florida format")
            self.assertGreater(conf, 0.5)

        # Invalid plates
        is_valid, _ = self.detector.validate_florida_plate("")
        self.assertFalse(is_valid)

        is_valid, _ = self.detector.validate_florida_plate("OVERSEVENCHARS")
        self.assertFalse(is_valid)

    def test_parse_alpr_result(self):
        res = self.detector.parse_alpr_result("FL-76BCDE", model_confidence=0.95)
        self.assertEqual(res["plate"], "76BCDE")
        self.assertEqual(res["state"], "FL")
        self.assertTrue(res["is_valid_format"])
        self.assertGreater(res["confidence"], 0.7)


class TestLookupService(unittest.TestCase):
    """Tests for vehicle specifications lookup and qualification enrichment."""

    def setUp(self):
        self.lookup = VehicleLookupService()

    def test_known_samples_lookup(self):
        data = self.lookup.lookup_plate("76BCDE", "FL")
        self.assertEqual(data["make"].upper(), "FORD")
        self.assertIn("F-150", data["model"])
        self.assertEqual(int(data["year"]), 2021)

        tesla_data = self.lookup.lookup_plate("SUNSHN", "FL")
        self.assertEqual(tesla_data["make"].upper(), "TESLA")
        self.assertIn("MODEL Y", tesla_data["model"].upper())

    def test_lead_qualification_enrichment(self):
        raw = self.lookup.lookup_plate("FLFAST", "FL")
        enriched = enrich_lead_metadata(raw, "FLFAST")
        self.assertTrue("vin_masked" in enriched and enriched["vin_masked"])
        self.assertTrue("lead_segment" in enriched and enriched["lead_segment"])
        self.assertTrue("outreach_pitch" in enriched and enriched["outreach_pitch"])
        self.assertTrue("fuel_type" in enriched and enriched["fuel_type"])
        self.assertTrue("drive_type" in enriched and enriched["drive_type"])

    def test_unseen_deterministic_lookup(self):
        res = self.lookup.lookup_plate("UNSEEN1", "FL")
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["make"])
        self.assertTrue(res["model"])
        self.assertTrue(res["year"])


class TestVehicleDatabase(unittest.TestCase):
    """Tests for SQLite homelab schema migrations, upserts, sightings, filters, and stats."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_leads.db")
        self.db = VehicleDatabase(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_migration_columns_exist(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(vehicle_leads)")
        cols = {r[1] for r in c.fetchall()}
        conn.close()

        required = [
            "id", "plate", "state", "make", "model", "year", "body_class",
            "engine_info", "vin_masked", "drive_type", "fuel_type",
            "lead_segment", "outreach_pitch", "image_path", "sightings_count",
            "confidence", "source", "notes", "created_at", "updated_at"
        ]
        for col in required:
            self.assertIn(col, cols, f"Database table missing expected column: {col}")

    def test_upsert_and_sightings_increment(self):
        lead_data = {
            "plate": "FLTEST",
            "state": "FL",
            "make": "FORD",
            "model": "F-150",
            "year": 2021,
            "body_class": "Pickup",
            "lead_segment": "Commercial Fleet",
            "outreach_pitch": "Fleet maintenance discount",
            "notes": "First sighting near dock"
        }

        # First sighting
        row_id_1 = self.db.upsert_lead(lead_data)
        self.assertGreater(row_id_1, 0)
        lead = self.db.get_lead("FLTEST")
        self.assertIsNotNone(lead)
        self.assertEqual(lead["sightings_count"], 1)
        self.assertEqual(lead["notes"], "First sighting near dock")

        # Second sighting: same plate & state
        lead_data_2 = {
            "plate": "FLTEST",
            "state": "FL",
            "notes": "Second sighting near warehouse"
        }
        row_id_2 = self.db.upsert_lead(lead_data_2)
        lead_after = self.db.get_lead("FLTEST")
        self.assertEqual(lead_after["sightings_count"], 2)
        self.assertEqual(lead_after["make"], "FORD")  # preserved
        self.assertEqual(lead_after["notes"], "Second sighting near warehouse")  # updated

        # Third sighting
        self.db.upsert_lead({"plate": "FLTEST", "state": "FL"})
        lead_third = self.db.get_lead("FLTEST")
        self.assertEqual(lead_third["sightings_count"], 3)

    def test_search_filters(self):
        leads = [
            {"plate": "TAG1", "state": "FL", "make": "FORD", "model": "F-150", "year": 2021, "body_class": "Pickup", "lead_segment": "Commercial Fleet"},
            {"plate": "TAG2", "state": "FL", "make": "TOYOTA", "model": "CAMRY", "year": 2017, "body_class": "Sedan", "lead_segment": "Daily Commuter"},
            {"plate": "TAG3", "state": "FL", "make": "TESLA", "model": "MODEL Y", "year": 2023, "body_class": "SUV", "lead_segment": "Electric & EV"},
        ]
        for l in leads:
            self.db.upsert_lead(l)

        # Search by make
        res_make = self.db.search_leads(make="Ford")
        self.assertEqual(len(res_make), 1)
        self.assertEqual(res_make[0]["plate"], "TAG1")

        # Search by year
        res_year = self.db.search_leads(year=2017)
        self.assertEqual(len(res_year), 1)
        self.assertEqual(res_year[0]["plate"], "TAG2")

        # Search by min_year
        res_min = self.db.search_leads(min_year=2020)
        self.assertEqual(len(res_min), 2)

        # Search by segment
        res_seg = self.db.search_leads(segment="Fleet")
        self.assertEqual(len(res_seg), 1)
        self.assertEqual(res_seg[0]["plate"], "TAG1")

        # Search by body_class
        res_body = self.db.search_leads(body_class="Sedan")
        self.assertEqual(len(res_body), 1)
        self.assertEqual(res_body[0]["plate"], "TAG2")

        # Search by general query
        res_query = self.db.search_leads(query="Model Y")
        self.assertEqual(len(res_query), 1)
        self.assertEqual(res_query[0]["plate"], "TAG3")

    def test_stats_analytics(self):
        self.db.upsert_lead({"plate": "A1", "state": "FL", "make": "FORD", "year": 2020, "lead_segment": "Fleet"})
        self.db.upsert_lead({"plate": "A1", "state": "FL"})  # 2 sightings
        self.db.upsert_lead({"plate": "A2", "state": "FL", "make": "TESLA", "year": 2022, "lead_segment": "EV"})

        stats = self.db.get_stats()
        self.assertEqual(stats["total_leads"], 2)
        self.assertEqual(stats["total_sightings"], 3)
        self.assertEqual(stats["average_year"], 2021.0)
        self.assertEqual(stats["by_make"]["FORD"], 1)
        self.assertEqual(stats["by_make"]["TESLA"], 1)
        self.assertEqual(stats["by_lead_segment"]["Fleet"], 1)
        self.assertEqual(stats["by_lead_segment"]["EV"], 1)


class TestExporters(unittest.TestCase):
    """Tests for CSV, JSON, and self-contained interactive HTML dashboard exporters."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.sample_leads = [
            {
                "id": 1,
                "plate": "76BCDE",
                "state": "FL",
                "make": "FORD",
                "model": "F-150",
                "year": 2021,
                "body_class": "Pickup",
                "engine_info": "3.5L V6 EcoBoost",
                "drive_type": "4WD",
                "fuel_type": "Gasoline",
                "vin_masked": "1FTFW1E****7821",
                "lead_segment": "Commercial Fleet",
                "outreach_pitch": "Fleet maintenance discount program",
                "sightings_count": 3,
                "confidence": 0.95,
                "source": "alpr_scanner",
                "notes": "Port of Miami sighting",
                "created_at": "2026-10-19 12:00:00",
                "updated_at": "2026-10-19 12:30:00"
            },
            {
                "id": 2,
                "plate": "SUNSHN",
                "state": "FL",
                "make": "TESLA",
                "model": "MODEL Y",
                "year": 2023,
                "body_class": "SUV",
                "engine_info": "Dual Motor Electric",
                "drive_type": "AWD",
                "fuel_type": "Electric (BEV)",
                "vin_masked": "5YJ3E1E****1024",
                "lead_segment": "Electric & Clean Energy",
                "outreach_pitch": "Home Level-2 charging installation bundle",
                "sightings_count": 1,
                "confidence": 0.98,
                "source": "alpr_scanner",
                "notes": "Supercharger bay",
                "created_at": "2026-10-19 13:00:00",
                "updated_at": "2026-10-19 13:00:00"
            }
        ]
        self.sample_stats = {
            "total_leads": 2,
            "total_sightings": 4,
            "average_year": 2022.0,
            "by_lead_segment": {
                "Commercial Fleet": 1,
                "Electric & Clean Energy": 1
            }
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_csv(self):
        csv_path = os.path.join(self.temp_dir.name, "leads.csv")
        out = export_csv(self.sample_leads, csv_path)
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 0)

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["plate"], "76BCDE")
            self.assertEqual(rows[0]["lead_segment"], "Commercial Fleet")
            self.assertEqual(rows[1]["plate"], "SUNSHN")

    def test_export_json(self):
        json_path = os.path.join(self.temp_dir.name, "leads.json")
        out = export_json(self.sample_leads, json_path)
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 0)

        with open(json_path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["plate"], "76BCDE")
            self.assertEqual(data[1]["model"], "MODEL Y")

    def test_export_html_dashboard(self):
        html_path = os.path.join(self.temp_dir.name, "outreach_leads.html")
        out = export_html_dashboard(self.sample_leads, self.sample_stats, html_path)
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 0)

        with open(html_path, mode="r", encoding="utf-8") as f:
            html = f.read()
            # Check essential dashboard components
            self.assertIn("PlateHound Leads Command Center", html)
            self.assertIn("FLORIDA", html)
            self.assertIn("76BCDE", html)
            self.assertIn("SUNSHN", html)
            self.assertIn("copyPitch", html)
            self.assertIn("searchInput", html)
            self.assertIn("Commercial Fleet", html)
            self.assertIn("Electric & Clean Energy", html)
            self.assertIn("Total Vehicle Leads", html)


if __name__ == "__main__":
    unittest.main()
