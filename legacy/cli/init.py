#!/usr/bin/env python3

from dotenv import load_dotenv
from create_card import add_qr_to_pdf_template  # Import the function from create_card
import os
import json
import pandas as pd
import glob
import zipfile
from datetime import datetime
import time

# Load environment variables from the .env file
load_dotenv()

REGISTRY_FILE = "processed_registry.json"

def get_latest_file(folder):
    """Returns the most recently created .xlsx file in the given folder."""
    files = glob.glob(os.path.join(folder, '*.xlsx'))
    if not files:
        raise FileNotFoundError(f"No .xlsx files found in {folder}")
    return max(files, key=os.path.getctime)

def load_registry(output_folder):
    """
    Loads the registry of already-processed attendee IDs.
    The registry is a JSON file at output/processed_registry.json with the format:
      { "<attendee_id>": {"name": "...", "processed_at": "YYYY-MM-DD HH:MM:SS"}, ... }
    Returns an empty dict if the file does not exist yet.
    """
    path = os.path.join(output_folder, REGISTRY_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_registry(output_folder, registry):
    """Persists the registry to disk."""
    path = os.path.join(output_folder, REGISTRY_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

def resolve_template(ticket_type, template_staff, template_speaker, template_attendee,
                     types_staff, types_speaker):
    """
    Resolves which PDF template to use based on the ticket type.
      TEMPLATE_STAFF    → ticket types in TICKET_TYPES_STAFF   (e.g. Helpers)
      TEMPLATE_SPEAKER  → ticket types in TICKET_TYPES_SPEAKER (e.g. Speakers)
      TEMPLATE_ATTENDEE → everything else (fallback)
    """
    if ticket_type in types_staff:
        return template_staff
    if ticket_type in types_speaker:
        return template_speaker
    return template_attendee

def process_excel_records(delete_temp_files, position_str, qr_size, excel_path, output_pdf_base,
                          col_attendee_id, col_first_name, col_last_name, col_ticket_type,
                          col_company,
                          template_staff, template_speaker, template_attendee,
                          types_staff, types_speaker, registry):
    """
    Reads the Eventbrite Excel export and generates one PDF credential per attendee.
    Skips attendees whose ID is already present in the registry (incremental mode).
    Selects the PDF template based on ticket type:
      - staff.pdf    → Helpers
      - speaker.pdf  → Speakers
      - atendee.pdf  → everything else
    Returns the updated registry and generation stats.
    """
    position = tuple(map(int, position_str.split(',')))
    df = pd.read_excel(excel_path)

    stats = {"generated": 0, "skipped": 0, "staff": 0, "speaker": 0, "attendee": 0}
    total = len(df)

    for index, row in df.iterrows():
        qr_data        = str(row[col_attendee_id])
        attendee_name  = row[col_first_name]
        attendee_lname = row[col_last_name]
        ticket_type    = row[col_ticket_type] if col_ticket_type in df.columns else ""
        attendee_company = str(row[col_company]) if col_company in df.columns and not pd.isna(row.get(col_company)) else ""

        # Skip empty/NaN rows (e.g. trailing blank rows in the Excel)
        if pd.isna(attendee_name) or pd.isna(attendee_lname) or qr_data in ("nan", ""):
            print(f"[{index + 1}/{total}] SKIP  Row {index + 1} — empty/invalid data, skipping")
            stats["skipped"] += 1
            continue

        # Incremental: skip already processed attendees
        if qr_data in registry:
            print(f"[{index + 1}/{total}] SKIP  {attendee_name} {attendee_lname} (already processed on {registry[qr_data]['processed_at']})")
            stats["skipped"] += 1
            continue

        template_pdf = resolve_template(
            ticket_type, template_staff, template_speaker, template_attendee,
            types_staff, types_speaker
        )

        output_pdf = f"{output_pdf_base}/attendee-{qr_data}.pdf"

        # Also skip if the output file already exists on disk (e.g. after a crash
        # before the registry could be saved)
        if os.path.exists(output_pdf):
            registry[qr_data] = {
                "name": f"{attendee_name} {attendee_lname}",
                "ticket_type": ticket_type,
                "template": os.path.basename(template_pdf),
                "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            print(f"[{index + 1}/{total}] SKIP  {attendee_name} {attendee_lname} (PDF already exists on disk)")
            stats["skipped"] += 1
            continue

        print(f"[{index + 1}/{total}] GEN   {attendee_name} {attendee_lname} | {ticket_type} → {os.path.basename(template_pdf)}")
        add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size,
                               delete_temp_files, attendee_name, attendee_lname, attendee_company)

        # Register as processed
        registry[qr_data] = {
            "name": f"{attendee_name} {attendee_lname}",
            "ticket_type": ticket_type,
            "template": os.path.basename(template_pdf),
            "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        stats["generated"] += 1

        if template_pdf == template_staff:
            stats["staff"] += 1
        elif template_pdf == template_speaker:
            stats["speaker"] += 1
        else:
            stats["attendee"] += 1

    print(f"\nSummary — Generated: {stats['generated']} | Skipped (already done): {stats['skipped']}")
    print(f"           Staff: {stats['staff']} | Speakers: {stats['speaker']} | Attendees: {stats['attendee']}")
    return registry

def compress_and_cleanup(output_pdf_base):
    """Compresses all newly generated PDFs into a timestamped zip and removes the originals.
    Skips the registry JSON file so it persists between runs."""
    pdf_files = [
        f for f in glob.glob(os.path.join(output_pdf_base, "*.pdf"))
    ]
    if not pdf_files:
        print("No new PDFs to compress.")
        return

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    zip_filename = os.path.join(output_pdf_base, f"attendees_{timestamp}.zip")

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in pdf_files:
            zipf.write(file_path, os.path.basename(file_path))
            os.remove(file_path)
    print(f"Created zip file: {zip_filename} ({len(pdf_files)} PDFs)")

def main(excel_file=None):
    start_time = time.time()
    print("Starting the process...")

    # Column names (Eventbrite export — Spanish locale by default)
    col_attendee_id = os.getenv("COL_ATTENDEE_ID", "Attendee #")
    col_first_name  = os.getenv("COL_FIRST_NAME",  "Final Attendee First Name")
    col_last_name   = os.getenv("COL_LAST_NAME",   "Final Attendee Last Name")
    col_ticket_type = os.getenv("COL_TICKET_TYPE", "Ticket Type")
    col_company     = os.getenv("COL_COMPANY",     "Empresa")

    # PDF templates per role
    template_staff    = os.getenv("TEMPLATE_STAFF",    "./templates/staff.pdf")
    template_speaker  = os.getenv("TEMPLATE_SPEAKER",  "./templates/speaker.pdf")
    template_attendee = os.getenv("TEMPLATE_ATTENDEE", "./templates/atendee.pdf")

    # Ticket type values that map to each template (comma-separated in .env)
    types_staff   = [t.strip() for t in os.getenv("TICKET_TYPES_STAFF",   "Helpers").split(",")]
    types_speaker = [t.strip() for t in os.getenv("TICKET_TYPES_SPEAKER", "Speakers").split(",")]

    # General settings
    position_str    = os.getenv("POSITION")
    qr_size         = int(os.getenv("QR_SIZE"))
    delete_temp_files = True
    input_folder    = os.getenv("INPUT_FOLDER")
    output_pdf_base = os.getenv("OUTPUT_FOLDER")

    excel_path = excel_file if excel_file else get_latest_file(input_folder)
    print(f"Input file:  {excel_path}")

    # Load registry of already-processed attendees (incremental mode)
    registry = load_registry(output_pdf_base)
    print(f"Registry:    {len(registry)} attendees already processed\n")

    try:
        registry = process_excel_records(
            delete_temp_files, position_str, qr_size, excel_path, output_pdf_base,
            col_attendee_id, col_first_name, col_last_name, col_ticket_type,
            col_company,
            template_staff, template_speaker, template_attendee,
            types_staff, types_speaker, registry
        )
    finally:
        # Always persist registry — even if an error occurs mid-batch
        save_registry(output_pdf_base, registry)
        print(f"Registry saved: {os.path.join(output_pdf_base, REGISTRY_FILE)}")

    compress_and_cleanup(output_pdf_base)

    elapsed = time.time() - start_time
    minutes, seconds = divmod(elapsed, 60)
    print(f"\nProcess completed in {int(minutes)} minutes and {int(seconds)} seconds.")

if __name__ == "__main__":
    import sys
    excel_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(excel_file)
