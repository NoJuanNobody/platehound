#!/usr/bin/env python3
import sys
import argparse
import json
from platehound.detector import FloridaPlateDetector
from platehound.lookup import VehicleLookupService
from platehound.database import VehicleDatabase

def format_row(cols, widths):
    return " | ".join(str(val).ljust(w) for val, w in zip(cols, widths))

def main():
    parser = argparse.ArgumentParser(
        description="PlateHound: Florida License Plate ALPR, Vehicle Specs Lookup & Leads Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python -m platehound.cli scan "FL-ABC123"
  python -m platehound.cli scan "76BCDE" --note "Observed near Miami marina"
  python -m platehound.cli batch-demo
  python -m platehound.cli list
  python -m platehound.cli search --make FORD
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: scan
    scan_p = subparsers.add_parser("scan", help="Scan raw plate string, enrich specs, and save lead")
    scan_p.add_argument("plate", help="License plate string (e.g. 'FL 76BCDE', 'ABC123')")
    scan_p.add_argument("--note", default="", help="Optional notes on the observation")
    scan_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")

    # Command: list
    list_p = subparsers.add_parser("list", help="List stored vehicle leads")
    list_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")
    list_p.add_argument("--json", action="store_true", help="Output JSON format")

    # Command: search
    search_p = subparsers.add_parser("search", help="Search vehicle leads")
    search_p.add_argument("--query", "-q", help="Search keyword across plate, make, or model")
    search_p.add_argument("--make", help="Filter by vehicle make")
    search_p.add_argument("--year", type=int, help="Filter by year")
    search_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")

    # Command: batch-demo
    batch_p = subparsers.add_parser("batch-demo", help="Run simulated batch ALPR ingestion on Florida plates")
    batch_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    detector = FloridaPlateDetector()
    lookup = VehicleLookupService()
    db = VehicleDatabase(getattr(args, "db", "platehound_leads.db"))

    if args.command == "scan":
        print(f"\n🐾 [PlateHound] Processing Input: '{args.plate}'...")
        detection = detector.parse_alpr_result(args.plate)
        print(f"   ✓ ALPR OCR Output : {detection['plate']} (Confidence: {detection['confidence']*100:.1f}%)")
        print(f"   ✓ State Validation: Florida ({'Valid' if detection['is_valid_format'] else 'Non-standard'})")
        
        print("   🔍 Querying Public Vehicle Specs (DHSMV / PlateQuery)...")
        specs = lookup.lookup_plate(detection['plate'], detection['state'])
        print(f"   🚘 Spec Match     : {specs['year']} {specs['make']} {specs['model']} ({specs['body_class']})")
        print(f"   ⚙️ Engine         : {specs['engine_info']}")

        lead_record = {
            "plate": detection["plate"],
            "state": "FL",
            "make": specs["make"],
            "model": specs["model"],
            "year": specs["year"],
            "body_class": specs["body_class"],
            "engine_info": specs["engine_info"],
            "confidence": detection["confidence"],
            "source": specs["source"],
            "notes": args.note
        }
        db.upsert_lead(lead_record)
        print(f"   💾 Saved to homelab database: {args.db}\n")

    elif args.command == "batch-demo":
        sample_plates = [
            ("FL-76BCDE", "Commercial fleet vehicle spot"),
            ("ABC 123", "South Beach drive-by"),
            ("XYZ-789", "Orlando distribution hub"),
            ("FLFAST", "Turnpike rest stop"),
            ("SUNSHN", "Tampa EV charging stall"),
            ("MIA305", "Wynwood parking lot")
        ]
        print(f"\n🚀 [PlateHound] Running Batch ALPR & Leads Enrichment ({len(sample_plates)} items)...")
        for raw, note in sample_plates:
            det = detector.parse_alpr_result(raw)
            spec = lookup.lookup_plate(det['plate'], det['state'])
            db.upsert_lead({
                "plate": det["plate"],
                "state": "FL",
                "make": spec["make"],
                "model": spec["model"],
                "year": spec["year"],
                "body_class": spec["body_class"],
                "engine_info": spec["engine_info"],
                "confidence": det["confidence"],
                "source": "batch_alpr_stream",
                "notes": note
            })
            print(f"   + Ingested: {det['plate']} -> {spec['year']} {spec['make']} {spec['model']}")
        print(f"✅ Successfully updated leads database. Total leads now: {db.count()}\n")

    elif args.command in ["list", "search"]:
        query = getattr(args, "query", None)
        make = getattr(args, "make", None)
        year = getattr(args, "year", None)
        leads = db.search_leads(query=query, make=make, year=year)

        if getattr(args, "json", False):
            print(json.dumps(leads, indent=2))
            return

        print(f"\n📋 [PlateHound Leads Database] ({len(leads)} matching records)")
        if not leads:
            print("   No vehicle leads found matching your criteria.")
            return

        headers = ["ID", "Plate", "State", "Year", "Make", "Model", "Body", "Notes"]
        widths = [4, 8, 5, 6, 12, 18, 12, 25]
        sep = "-" * (sum(widths) + len(widths) * 3)

        print(sep)
        print(format_row(headers, widths))
        print(sep)
        for r in leads:
            row_data = [
                r["id"],
                r["plate"],
                r["state"],
                r["year"] or "-",
                r["make"] or "-",
                r["model"] or "-",
                r["body_class"] or "-",
                (r["notes"] or "")[:25]
            ]
            print(format_row(row_data, widths))
        print(sep + "\n")

if __name__ == "__main__":
    main()
