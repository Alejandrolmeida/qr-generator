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
from reportlab.lib import colors

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

def add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size, delete_temp_files, attendee_name, attendee_lastame, attendee_company):
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

    # Create a new temporary PDF to draw the QR code, attendee name, last name, and company
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf_file:
        temp_pdf_path = temp_pdf_file.name
        c = canvas.Canvas(temp_pdf_path, pagesize=letter)
        
        # Calculate horizontal center for the QR code
        page_width = letter[0]
        qr_x = (page_width - qr_size) / 2
        qr_y = position[1] - 25

        # Draw the QR code centered horizontally
        renderPDF.draw(drawing, c, qr_x, qr_y)
        
        # Define maximum text width and calculate horizontal center for text
        max_text_width = 240  # Fixed width for the text
        
        # Draw attendee name centered horizontally
        attendee_name_upper = attendee_name.upper()
        font_size = adjust_font_size(c, attendee_name_upper, max_text_width)
        c.setFont("DejaVuSans-Bold", font_size)
        c.setFillColor(colors.black)
        text_width = c.stringWidth(attendee_name_upper, "DejaVuSans-Bold", font_size)
        text_x = (page_width - text_width) / 2
        text_y = qr_y + qr_size + 115
        c.drawString(text_x, text_y, attendee_name_upper)

        # Draw attendee last name centered horizontally
        attendee_lastame_upper = attendee_lastame.upper()
        font_size = adjust_font_size(c, attendee_lastame_upper, max_text_width)
        c.setFont("DejaVuSans-Bold", font_size)
        text_width = c.stringWidth(attendee_lastame_upper, "DejaVuSans-Bold", font_size)
        text_x = (page_width - text_width) / 2
        text_y = text_y - 45
        c.drawString(text_x, text_y, attendee_lastame_upper)

        # Draw attendee company centered horizontally in color #005BAB if not empty
        if attendee_company:
            attendee_company_upper = attendee_company.upper()
            font_size = adjust_font_size(c, attendee_company_upper, max_text_width)
            c.setFont("DejaVuSans-Bold", font_size)
            c.setFillColor(colors.HexColor("#005BAB"))  # Set text color to #005BAB
            text_width = c.stringWidth(attendee_company_upper, "DejaVuSans-Bold", font_size)
            text_x = (page_width - text_width) / 2
            text_y = text_y - 55
            c.drawString(text_x, text_y, attendee_company_upper)
        
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
