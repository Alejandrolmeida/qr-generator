#!/usr/bin/env python3

import os
import time
import sys
import random
import argparse
from dotenv import load_dotenv
from create_card import add_qr_to_pdf_template  # Import the functions from create_card

# Load environment variables from the .env file
load_dotenv()

def generate_pdf(name, lastname, number, delete_temp_files, template_pdf, position_str, qr_size, output_pdf_base):
    position = tuple(map(int, position_str.split(','))) 
    qr_data = number
    attendee_name = name
    attendee_lastame = lastname
    output_pdf = f"{output_pdf_base}/attendee-{qr_data}.pdf"  # Generate a unique file name for each record
    
    print(f"Processing record: {attendee_name} {attendee_lastame}")
    add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size, delete_temp_files, attendee_name, attendee_lastame)

def main(name, lastname, number):    
    start_time = time.time()
    print("Starting the process...")

    template_pdf = os.getenv("TEMPLATE_PDF")
    position_str = os.getenv("POSITION")
    qr_size = int(os.getenv("QR_SIZE"))  
    delete_temp_files = os.getenv("DELETE_TEMP_FILES", "False").lower() in ("true", "1", "t")
    output_pdf_base = os.getenv("OUTPUT_FOLDER")

    generate_pdf(name, lastname, number, delete_temp_files, template_pdf, position_str, qr_size, output_pdf_base)

    end_time = time.time()
    elapsed_time = end_time - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    print(f"Process completed in {int(minutes)} minutes and {int(seconds)} seconds.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a PDF with QR code for an attendee.")
    parser.add_argument("-r", "--random", action="store_true", help="Generate a random number for the attendee.")
    parser.add_argument("number", nargs="?", help="Attendee number (optional if -r is used).")
    args = parser.parse_args()

    name = input("Enter Attendee name: ")
    lastname = input("Enter Attendee lastname: ")

    if args.random:
        number = str(random.randint(20000000000, 30000000000))
        print(f"Generated random number: {number}")
    elif args.number:
        number = args.number
    else:
        number = input("Enter Attendee number: ")

    main(name, lastname, number)