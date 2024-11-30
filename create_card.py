#!/usr/bin/env python3

import fitz  # PyMuPDF
import qrcode
import qrcode.image.svg
from io import BytesIO
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import shutil
import os
import tempfile
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Register the TTF font
pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'fonts/DejaVuSans-Bold.ttf'))

def generate_qr_code_svg(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Higher error correction
        box_size=10,
        border=4,
    )
    qr.add_data(data)    
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
    buffer = BytesIO()
    img.save(buffer)
    buffer.seek(0)
    return buffer

def scale_drawing(drawing, width, height):
    # Calculate the minimum dimensions of the drawing
    min_width = drawing.width
    min_height = drawing.height

    # Scale the drawing to the specified dimensions
    drawing.width = width
    drawing.height = height
    drawing.scale(width / min_width, height / min_height)
    return drawing

def adjust_font_size(c, text, max_width, initial_font_size=30, min_font_size=10):
    font_size = initial_font_size
    while font_size >= min_font_size:
        c.setFont("DejaVuSans-Bold", font_size)
        text_width = c.stringWidth(text, "DejaVuSans-Bold", font_size)
        if text_width <= max_width:
            return font_size
        font_size -= 1
    return min_font_size

def add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size, delete_temp_files, attendee_name, attendee_lastame):
    # Make a copy of the template PDF
    shutil.copyfile(template_pdf, output_pdf)

    # Generate the QR code in SVG
    qr_svg = generate_qr_code_svg(qr_data)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as temp_svg_file:
        temp_svg_file.write(qr_svg.read())
        temp_svg_path = temp_svg_file.name

    # Convert SVG to RLG (ReportLab Graphics)
    drawing = svg2rlg(temp_svg_path)
    drawing = scale_drawing(drawing, qr_size, qr_size)

    # Create a new temporary PDF to draw the QR code and attendee name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf_file:
        temp_pdf_path = temp_pdf_file.name
        c = canvas.Canvas(temp_pdf_path, pagesize=letter)
        
        # Draw the QR code at the specified position
        renderPDF.draw(drawing, c, position[0], position[1])
        
        # Draw the attendee name in uppercase next to the QR code
        attendee_name_upper = attendee_name.upper()
        max_text_width = 300  # Define the fixed width for the text
        text_x = position[0] + qr_size + 10  # Adjust the x position as needed
        text_y = position[1] + (qr_size / 4 * 3) - 20
        font_size = adjust_font_size(c, attendee_name_upper, max_text_width)
        c.setFont("DejaVuSans-Bold", font_size)
        c.drawString(text_x, text_y, attendee_name_upper)

        # Draw the attendee last name in uppercase next to the QR code
        attendee_lastame_upper = attendee_lastame.upper()
        text_y = position[1] + (qr_size / 4) + (qr_size / 10)
        font_size = adjust_font_size(c, attendee_lastame_upper, max_text_width)
        c.setFont("DejaVuSans-Bold", font_size)
        c.drawString(text_x, text_y, attendee_lastame_upper)
        
        c.save()

    # Open the destination PDF file and draw the QR code and attendee name on it
    doc = fitz.open(output_pdf)
    page = doc.load_page(0)
    
    # Insert the content of the temporary PDF into the destination page
    qr_doc = fitz.open(temp_pdf_path)
    qr_page = qr_doc.load_page(0)
    page.show_pdf_page(page.rect, qr_doc, 0)

    use_local_temp_dir = os.getenv("USE_LOCAL_TEMP_DIR", "False").lower() in ("true", "1", "t")
    
    # Save the modified PDF file to a temporary file
    if use_local_temp_dir:
        temp_file = NamedTemporaryFile(delete=False, suffix=".pdf", dir=os.getcwd())
    else:
        temp_file = NamedTemporaryFile(delete=False, suffix=".pdf")

    temp_output_path = temp_file.name
    temp_file.close()

    doc.save(temp_output_path, deflate=True)
    
    # Replace the destination file with the temporary file
    shutil.move(temp_output_path, output_pdf)
    doc.close()

    # Delete temporary files if delete_temp_files is True
    if delete_temp_files:
        os.remove(temp_svg_path)        
        os.remove(temp_pdf_path)
    
    print(f"Modified PDF saved at {output_pdf}")

def main(qr_data, output_pdf):
    template_pdf = os.getenv("TEMPLATE_PDF")
    position_str = os.getenv("POSITION")
    qr_size = int(os.getenv("QR_SIZE"))  # Convert qr_size to integer
    position = tuple(map(int, position_str.split(',')))

    # Define the delete_temp_files variable
    delete_temp_files = True

    add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size, delete_temp_files)
