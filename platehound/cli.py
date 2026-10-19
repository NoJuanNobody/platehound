#!/usr/bin/env python3
import sys
import os
import argparse
import json
from typing import Dict, Any, List, Optional

from platehound.detector import FloridaPlateDetector
from platehound.lookup import VehicleLookupService
from platehound.database import VehicleDatabase
from platehound.exporter import export_csv, export_json, export_html_dashboard


def enrich_lead_metadata(specs: Dict[str, Any], plate: str) -> Dict[str, Any]:
    """
    Enriches vehicle record with masked VIN, drive type, fuel type,
    lead segment, and outreach pitch if not already populated.
    """
    record = dict(specs)
    make = str(record.get("make") or "").upper()
    model = str(record.get("model") or "").upper()
    body = str(record.get("body_class") or "").upper()
    engine = str(record.get("engine_info") or "")
    year = record.get("year") or 2021
    plate_clean = plate.upper().strip()

    # 1. Drive type
    if not record.get("drive_type"):
        if any(k in body for k in ["PICKUP", "TRUCK"]) or any(k in model for k in ["WRANGLER", "F-150", "SILVERADO"]):
            record["drive_type"] = "4WD"
        elif any(k in make for k in ["PORSCHE", "TESLA", "SUBARU", "AUDI"]) or "AWD" in model:
            record["drive_type"] = "AWD"
        elif "CORVETTE" in model or "MUSTANG" in model or "CAMARO" in model:
            record["drive_type"] = "RWD"
        else:
            record["drive_type"] = "FWD"

    # 2. Fuel type
    if not record.get("fuel_type"):
        if "TESLA" in make or "ELECTRIC" in engine.upper() or "EV" in plate_clean or "DUAL MOTOR" in engine.upper():
            record["fuel_type"] = "Electric (BEV)"
        elif "HYBRID" in engine.upper() or "HYBRID" in model:
            record["fuel_type"] = "Hybrid"
        elif "DIESEL" in engine.upper():
            record["fuel_type"] = "Diesel"
        else:
            record["fuel_type"] = "Gasoline"

    # 3. Masked VIN
    if not record.get("vin_masked"):
        vin_prefix = "1FTFW1E" if "FORD" in make else (
            "1G1YY22" if "CHEV" in make else (
                "5YJ3E1E" if "TESLA" in make else (
                    "WP0AB2A" if "PORSCHE" in make else (
                        "1C4HJXF" if "JEEP" in make else "4T1B11H"
                    )
                )
            )
        )
        suffix = "".join(f"{ord(c)%10}" for c in plate_clean[-4:] if c.isalnum())
        record["vin_masked"] = f"{vin_prefix}****{suffix.zfill(4)}"

    # 4. Lead Segment & Outreach Pitch
    if not record.get("lead_segment") or not record.get("outreach_pitch"):
        if "TESLA" in make or record["fuel_type"] == "Electric (BEV)":
            seg = "Electric & Clean Energy"
            pitch = f"Upgrade your {year} {make} {model} with high-amperage Level-2 smart homelab charging & battery wellness inspection."
        elif "PORSCHE" in make or any(k in model for k in ["CORVETTE", "911", "CARRERA", "FERRARI"]):
            seg = "Exotic & Performance"
            pitch = f"Exclusive detailing, paint protection film, and track-ready performance concierge for your {year} {make} {model}."
        elif any(k in body for k in ["PICKUP", "TRUCK"]) or any(k in model for k in ["F-150", "SILVERADO", "RAM"]):
            seg = "Commercial Fleet & Work"
            pitch = f"Commercial fleet maintenance package & tax-advantaged trade-in appraisal on your {year} {make} {model}."
        elif "WRANGLER" in model or "JEEP" in make or "BRONCO" in model:
            seg = "Off-Road & Adventure"
            pitch = f"Trail-ready suspension outfitting, overland armor, and custom accessory bundles for your {year} {make} {model}."
        elif int(year) < 2018:
            seg = "Pre-Owned Trade Candidate"
            pitch = f"High-demand trade-in bonus: receive top-market instant cash value towards modern upgrade on your {year} {make} {model}."
        else:
            seg = "Daily Commuter Fleet"
            pitch = f"Comprehensive extended warranty & complimentary multi-point digital inspection for your {year} {make} {model}."

        if not record.get("lead_segment"):
            record["lead_segment"] = seg
        if not record.get("outreach_pitch"):
            record["outreach_pitch"] = pitch

    return record


def format_row(cols: List[Any], widths: List[int]) -> str:
    return " | ".join(str(val)[:w].ljust(w) for val, w in zip(cols, widths))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="platehound",
        description="PlateHound: Florida License Plate ALPR, Vehicle Specs Lookup & Leads Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  platehound scan "FL-76BCDE" --note "Observed near Port of Miami"
  platehound scan-image ./plates/sample1.jpg
  platehound generate-plates
  platehound batch-demo
  platehound list
  platehound search --query "Ford" --segment "Fleet"
  platehound stats
  platehound export --format html --output outreach_leads.html
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: scan
    scan_p = subparsers.add_parser("scan", help="Scan raw plate string, enrich specs, and save lead")
    scan_p.add_argument("plate", help="License plate string (e.g. 'FL 76BCDE', 'ABC123')")
    scan_p.add_argument("--note", default="", help="Optional notes on the observation")
    scan_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")

    # Command: scan-image
    img_p = subparsers.add_parser("scan-image", help="Detect plate from image, enrich specs, and save lead")
    img_p.add_argument("image_path", help="Path to vehicle or license plate image file")
    img_p.add_argument("--note", default="", help="Optional notes on the observation")
    img_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")

    # Command: generate-plates
    gen_p = subparsers.add_parser("generate-plates", help="Generate synthetic Florida license plate samples")

    # Command: batch-demo
    batch_p = subparsers.add_parser("batch-demo", help="Run simulated batch ALPR ingestion on 8 Florida plates")
    batch_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")

    # Command: list
    list_p = subparsers.add_parser("list", help="List stored vehicle leads")
    list_p.add_argument("--query", "-q", help="Search keyword across plate, make, model, notes, or segment")
    list_p.add_argument("--make", help="Filter by vehicle make")
    list_p.add_argument("--year", type=int, help="Filter by exact year")
    list_p.add_argument("--min-year", type=int, help="Filter by minimum vehicle year")
    list_p.add_argument("--segment", help="Filter by lead segment")
    list_p.add_argument("--body", help="Filter by body class")
    list_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")
    list_p.add_argument("--json", action="store_true", help="Output JSON format")

    # Command: search
    search_p = subparsers.add_parser("search", help="Search vehicle leads with filters")
    search_p.add_argument("--query", "-q", help="Search keyword across plate, make, model, notes, or segment")
    search_p.add_argument("--make", help="Filter by vehicle make")
    search_p.add_argument("--year", type=int, help="Filter by exact year")
    search_p.add_argument("--min-year", type=int, help="Filter by minimum vehicle year")
    search_p.add_argument("--segment", help="Filter by lead segment")
    search_p.add_argument("--body", help="Filter by body class")
    search_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")
    search_p.add_argument("--json", action="store_true", help="Output JSON format")

    # Command: stats
    stats_p = subparsers.add_parser("stats", help="Display homelab leads analytics and breakdowns")
    stats_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")
    stats_p.add_argument("--json", action="store_true", help="Output stats in JSON format")

    # Command: export
    export_p = subparsers.add_parser("export", help="Export leads to CSV, JSON, or interactive HTML dashboard")
    export_p.add_argument("--format", choices=["csv", "json", "html"], default="html", help="Export file format")
    export_p.add_argument("--output", "-o", help="Target output file path")
    export_p.add_argument("--db", default="platehound_leads.db", help="Path to SQLite database")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    detector = FloridaPlateDetector()
    lookup = VehicleLookupService()
    db = VehicleDatabase(getattr(args, "db", "platehound_leads.db"))

    # Handler: scan
    if args.command == "scan":
        print(f"\n🐾 [PlateHound] Processing Input: '{args.plate}'...")
        detection = detector.parse_alpr_result(args.plate)
        print(f"   ✓ ALPR OCR Output : {detection['plate']} (Confidence: {detection['confidence']*100:.1f}%)")
        print(f"   ✓ State Validation: Florida ({'Valid' if detection['is_valid_format'] else 'Non-standard'})")

        print("   🔍 Querying Public Vehicle Specs (DHSMV / PlateQuery)...")
        raw_specs = lookup.lookup_plate(detection['plate'], detection['state'])
        specs = enrich_lead_metadata(raw_specs, detection['plate'])
        print(f"   🚘 Spec Match     : {specs['year']} {specs['make']} {specs['model']} ({specs['body_class']})")
        print(f"   ⚙️ Engine / Fuel  : {specs['engine_info']} ({specs.get('fuel_type')}, {specs.get('drive_type')})")
        print(f"   🎯 Lead Segment   : {specs.get('lead_segment')}")
        print(f"   ⚡ Tailored Pitch : \"{specs.get('outreach_pitch')}\"")

        lead_record = {
            "plate": detection["plate"],
            "state": "FL",
            "make": specs.get("make"),
            "model": specs.get("model"),
            "year": specs.get("year"),
            "body_class": specs.get("body_class"),
            "engine_info": specs.get("engine_info"),
            "vin_masked": specs.get("vin_masked"),
            "drive_type": specs.get("drive_type"),
            "fuel_type": specs.get("fuel_type"),
            "lead_segment": specs.get("lead_segment"),
            "outreach_pitch": specs.get("outreach_pitch"),
            "image_path": None,
            "confidence": detection["confidence"],
            "source": specs.get("source", "alpr_scanner"),
            "notes": args.note
        }
        db.upsert_lead(lead_record)
        stored = db.get_lead(detection["plate"], "FL")
        sightings = stored.get("sightings_count", 1) if stored else 1
        print(f"   💾 Saved to homelab database: {args.db} (Sightings count: {sightings})\n")

    # Handler: scan-image
    elif args.command == "scan-image":
        print(f"\n📷 [PlateHound] Scanning Image: '{args.image_path}'...")
        if hasattr(detector, "detect_and_read_image"):
            detection = detector.detect_and_read_image(args.image_path)
        else:
            base_name = os.path.splitext(os.path.basename(args.image_path))[0]
            detection = detector.parse_alpr_result(base_name)

        plate = detection.get("plate", "")
        print(f"   ✓ Detected Plate  : {plate} (Confidence: {detection.get('confidence', 1.0)*100:.1f}%)")

        raw_specs = lookup.lookup_plate(plate, "FL")
        specs = enrich_lead_metadata(raw_specs, plate)

        lead_record = {
            "plate": plate,
            "state": "FL",
            "make": specs.get("make"),
            "model": specs.get("model"),
            "year": specs.get("year"),
            "body_class": specs.get("body_class"),
            "engine_info": specs.get("engine_info"),
            "vin_masked": specs.get("vin_masked"),
            "drive_type": specs.get("drive_type"),
            "fuel_type": specs.get("fuel_type"),
            "lead_segment": specs.get("lead_segment"),
            "outreach_pitch": specs.get("outreach_pitch"),
            "image_path": args.image_path,
            "confidence": detection.get("confidence", 1.0),
            "source": "image_detector",
            "notes": args.note or f"Ingested from image: {os.path.basename(args.image_path)}"
        }
        db.upsert_lead(lead_record)
        stored = db.get_lead(plate, "FL")
        sightings = stored.get("sightings_count", 1) if stored else 1
        print(f"   🚘 Spec Match     : {specs['year']} {specs['make']} {specs['model']} ({specs['body_class']})")
        print(f"   🎯 Lead Segment   : {specs.get('lead_segment')}")
        print(f"   💾 Saved to homelab database: {args.db} (Sightings: {sightings})\n")

    # Handler: generate-plates
    elif args.command == "generate-plates":
        try:
            from platehound import plate_generator
            plates = plate_generator.generate_sample_plates()
            print(f"\n🚗 [PlateHound] Generated {len(plates)} Sample Florida Plates:")
            for p in plates:
                print(f"   • {p}")
            print()
        except (ImportError, AttributeError):
            print("\n🚗 [PlateHound] Synthetic Florida Plates:")
            fallback_plates = ["FL-76BCDE", "ABC 123", "XYZ-789", "FLFAST", "SUNSHN", "MIA305", "GATOR1", "305EV1"]
            for p in fallback_plates:
                print(f"   • {p}")
            print()

    # Handler: batch-demo
    elif args.command == "batch-demo":
        sample_plates = [
            ("FL-76BCDE", "Commercial fleet vehicle spot near Port of Miami"),
            ("ABC 123", "South Beach ocean drive cruiser"),
            ("XYZ-789", "Orlando distribution hub logistics vehicle"),
            ("FLFAST", "Turnpike rest stop high performance coupe"),
            ("SUNSHN", "Tampa EV supercharger bay"),
            ("MIA305", "Wynwood Art District utility vehicle"),
            ("GATOR1", "Gainesville campus tailgate pickup"),
            ("305EV1", "Brickell financial district electric commuter")
        ]
        print(f"\n🚀 [PlateHound] Running Batch ALPR & Leads Enrichment ({len(sample_plates)} items)...")
        for raw, note in sample_plates:
            det = detector.parse_alpr_result(raw)
            raw_spec = lookup.lookup_plate(det['plate'], det['state'])
            spec = enrich_lead_metadata(raw_spec, det['plate'])

            db.upsert_lead({
                "plate": det["plate"],
                "state": "FL",
                "make": spec.get("make"),
                "model": spec.get("model"),
                "year": spec.get("year"),
                "body_class": spec.get("body_class"),
                "engine_info": spec.get("engine_info"),
                "vin_masked": spec.get("vin_masked"),
                "drive_type": spec.get("drive_type"),
                "fuel_type": spec.get("fuel_type"),
                "lead_segment": spec.get("lead_segment"),
                "outreach_pitch": spec.get("outreach_pitch"),
                "image_path": None,
                "confidence": det.get("confidence", 1.0),
                "source": "batch_alpr_stream",
                "notes": note
            })
            lead_in_db = db.get_lead(det["plate"], "FL")
            sightings = lead_in_db.get("sightings_count", 1) if lead_in_db else 1
            print(f"   + Ingested: {det['plate']:<8} -> {spec['year']} {spec['make']:<10} {spec['model']:<16} [{spec.get('lead_segment')}] (Sightings: {sightings})")

        stats = db.get_stats()
        print(f"\n✅ Batch Ingestion Complete! Database Summary:")
        print(f"   • Total Leads    : {stats['total_leads']}")
        print(f"   • Total Sightings: {stats['total_sightings']}")
        print(f"   • Avg Fleet Year : {stats.get('average_year') or 'N/A'}")
        print(f"   • Lead Segments  : {len(stats['by_lead_segment'])} categories")
        print()

    # Handler: list and search
    elif args.command in ["list", "search"]:
        query = getattr(args, "query", None)
        make = getattr(args, "make", None)
        year = getattr(args, "year", None)
        min_year = getattr(args, "min_year", None)
        segment = getattr(args, "segment", None)
        body = getattr(args, "body", None)

        leads = db.search_leads(
            query=query,
            make=make,
            year=year,
            min_year=min_year,
            segment=segment,
            body_class=body
        )

        if getattr(args, "json", False):
            print(json.dumps(leads, indent=2))
            return

        print(f"\n📋 [PlateHound Leads Database] ({len(leads)} matching records)")
        if not leads:
            print("   No vehicle leads found matching your criteria.\n")
            return

        headers = ["ID", "Plate", "State", "Year", "Make", "Model", "Segment", "Sightings", "Pitch Hook"]
        widths = [4, 8, 5, 5, 11, 16, 22, 9, 36]
        sep = "-" * (sum(widths) + len(widths) * 3)

        print(sep)
        print(format_row(headers, widths))
        print(sep)
        for r in leads:
            row_data = [
                r.get("id", ""),
                r.get("plate", ""),
                r.get("state", "FL"),
                r.get("year") or "-",
                r.get("make") or "-",
                r.get("model") or "-",
                (r.get("lead_segment") or "-")[:22],
                f"👁️ {r.get('sightings_count', 1)}",
                (r.get("outreach_pitch") or r.get("notes") or "")[:36]
            ]
            print(format_row(row_data, widths))
        print(sep + "\n")

    # Handler: stats
    elif args.command == "stats":
        stats = db.get_stats()
        if getattr(args, "json", False):
            print(json.dumps(stats, indent=2))
            return

        print("\n📊 ========================================================")
        print("   🐾 PLATEHOUND HOMELAB LEADS DATABASE ANALYTICS")
        print("   ========================================================")
        print(f"   • Total Leads Registered : {stats['total_leads']}")
        print(f"   • Total ALPR Sightings   : {stats['total_sightings']}")
        print(f"   • Average Vehicle Year   : {stats.get('average_year') or 'N/A'}")

        print("\n   🏷️  LEAD SEGMENT BREAKDOWN:")
        for seg, count in stats.get("by_lead_segment", {}).items():
            pct = (count / stats["total_leads"] * 100) if stats["total_leads"] else 0
            bar = "█" * int(pct / 5)
            print(f"     - {seg:<26}: {count:>3} leads ({pct:5.1f}%) {bar}")

        print("\n   🚘 TOP VEHICLE MAKES:")
        for make, count in list(stats.get("by_make", {}).items())[:8]:
            pct = (count / stats["total_leads"] * 100) if stats["total_leads"] else 0
            bar = "▓" * int(pct / 5)
            print(f"     - {make:<16}: {count:>3} vehicles ({pct:5.1f}%) {bar}")
        print("   ========================================================\n")

    # Handler: export
    elif args.command == "export":
        fmt = getattr(args, "format", "html").lower()
        leads = db.search_leads()
        stats = db.get_stats()

        if not args.output:
            default_names = {
                "csv": "platehound_leads.csv",
                "json": "platehound_leads.json",
                "html": "outreach_leads.html"
            }
            output_file = default_names.get(fmt, "outreach_leads.html")
        else:
            output_file = args.output

        if fmt == "csv":
            res = export_csv(leads, output_file)
        elif fmt == "json":
            res = export_json(leads, output_file)
        else:
            res = export_html_dashboard(leads, stats, output_file)

        print(f"\n📦 [PlateHound Export] Successfully exported {len(leads)} leads to {fmt.upper()}:")
        print(f"   ✓ File: {os.path.abspath(res)}\n")


if __name__ == "__main__":
    main()
