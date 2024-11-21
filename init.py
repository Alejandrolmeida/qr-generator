#!/usr/bin/env python3

from dotenv import load_dotenv
from create_card import add_qr_to_pdf_template  # Import the function from create_card
import os
import pandas as pd
import glob
import zipfile
from datetime import datetime
import time

# Load environment variables from the .env file
load_dotenv()

def get_latest_file(folder):
    files = glob.glob(os.path.join(folder, '*'))
    latest_file = max(files, key=os.path.getctime)
    return latest_file

def process_excel_records(delete_temp_files, template_pdf, position_str, qr_size, excel_path, output_pdf_base):
    position = tuple(map(int, position_str.split(',')))    
    df = pd.read_excel(excel_path)    

    # Iterate over the records in the table
    for index, row in df.iterrows():
        qr_data = row['Attendee #']
        attendee_name = row['Final Attendee First Name']
        attendee_lastame = row['Final Attendee Last Name']
        output_pdf = f"{output_pdf_base}/attendee-{qr_data}.pdf"  # Generate a unique file name for each record
        print(f"Processing record {index + 1}/{len(df)}: {attendee_name} {attendee_lastame}")
        add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size, delete_temp_files, attendee_name, attendee_lastame)

def compress_and_cleanup(output_pdf_base):
    # Get the current date and time
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    
    # Create a zip file with the timestamp in the name
    zip_filename = os.path.join(output_pdf_base, f"attendees_{timestamp}.zip")
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for root, _, files in os.walk(output_pdf_base):
            for file in files:
                if file.endswith(".pdf"):
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.basename(file_path))
                    os.remove(file_path)  # Delete the file after adding it to the zip
    print(f"Created zip file: {zip_filename}")

def main(excel_file=None):    
    start_time = time.time()
    print("Starting the process...")

    template_pdf = os.getenv("TEMPLATE_PDF")
    position_str = os.getenv("POSITION")
    qr_size = int(os.getenv("QR_SIZE"))  
    delete_temp_files = True
    input_folder = os.getenv("INPUT_FOLDER")
    output_pdf_base = os.getenv("OUTPUT_FOLDER")

    if excel_file:
        excel_path = excel_file
    else:
        excel_path = get_latest_file(input_folder)

    process_excel_records(delete_temp_files, template_pdf, position_str, qr_size, excel_path, output_pdf_base)
    compress_and_cleanup(output_pdf_base)

    end_time = time.time()
    elapsed_time = end_time - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    print(f"Process completed in {int(minutes)} minutes and {int(seconds)} seconds.")

if __name__ == "__main__":
    import sys
    excel_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(excel_file)