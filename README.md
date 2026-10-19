# PlateHound 🐾🚗
**Automated Florida ALPR, Vehicle Specs Resolver & Homelab Leads Database**

PlateHound is an open-source pipeline that scans Florida license plates via OCR/YOLO, enriches them with public non-personal specifications (Make, Model, Year, Body Class, Powertrain), and compiles them into a fast, local SQLite leads database.

---

## ⚡ Quick Start

```bash
# 1. Clone repository
git clone https://github.com/your-username/platehound.git
cd platehound

# 2. Ingest single plate
python3 -m platehound.cli scan "FL-76BCDE" --note "Commercial pickup on Biscayne Blvd"

# 3. Ingest demo stream
python3 -m platehound.cli batch-demo

# 4. Search and view leads list
python3 -m platehound.cli search --make FORD
python3 -m platehound.cli list
```

## 🛠 Features
- **Florida Plate Parsing & ALPR Normalization**: Regex-validated formatting for FL standard, commercial, and vanity plates.
- **Spec Enrichment**: Resolves Make, Model, Year, Body Class, and Engine specs using public vehicle data APIs.
- **Privacy First**: Captures zero Personally Identifiable Information (no names, addresses, or owner data). Only vehicle specs and observation timestamps.
- **Homelab Database**: Embedded SQLite schema optimized for fast querying, filtering, and JSON/CSV export.
