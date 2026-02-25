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
from reportlab.lib import colors
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

def add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size, delete_temp_files, attendee_name, attendee_lastame, attendee_company=""):
    # Make a copy of the template PDF
    shutil.copyfile(template_pdf, output_pdf)

    # Read template dimensions so the overlay is created at the exact same size.
    # This avoids any scaling when the overlay is merged, keeping positions pixel-perfect.
    with fitz.open(template_pdf) as _tmpl:
        tmpl_w = _tmpl[0].rect.width
        tmpl_h = _tmpl[0].rect.height

    # Generate the QR code in SVG
    qr_svg = generate_qr_code_svg(qr_data)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as temp_svg_file:
        temp_svg_file.write(qr_svg.read())
        temp_svg_path = temp_svg_file.name

    # Convert SVG to RLG (ReportLab Graphics)
    drawing = svg2rlg(temp_svg_path)
    drawing = scale_drawing(drawing, qr_size, qr_size)

    # Create overlay PDF at the SAME dimensions as the template.
    # ReportLab uses y=0 at bottom; position=(x, y_bottom) in these coordinates.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf_file:
        temp_pdf_path = temp_pdf_file.name

    c = canvas.Canvas(temp_pdf_path, pagesize=(tmpl_w, tmpl_h))

    # ── QR code ────────────────────────────────────────────────────────────────
    # position = (qr_x, qr_y_bottom): bottom-left of QR in ReportLab coords.
    # Designed so the QR is horizontally centered inside the white box.
    renderPDF.draw(drawing, c, position[0], position[1])

    # ── Attendee name: centered above the QR code ───────────────────────────
    # Text is centered on the page (white box center == page center horizontally).
    page_cx = tmpl_w / 2
    # Max text width = white box width minus 10 pt margin on each side
    max_text_width = tmpl_w - (position[0] * 2) - 4
    qr_top = position[1] + qr_size  # top edge of QR in RL coords (y from bottom)

    # Last name — first line above QR
    last_upper = attendee_lastame.upper()
    font_last = adjust_font_size(c, last_upper, max_text_width, initial_font_size=22)
    c.setFont("DejaVuSans-Bold", font_last)
    y_last = qr_top + 10
    c.drawCentredString(page_cx, y_last, last_upper)

    # First name — second line above last name
    first_upper = attendee_name.upper()
    font_first = adjust_font_size(c, first_upper, max_text_width, initial_font_size=22)
    c.setFont("DejaVuSans-Bold", font_first)
    y_first = y_last + font_last + 6
    c.drawCentredString(page_cx, y_first, first_upper)

    # Company — optional third line, rendered in brand blue #005BAB
    if attendee_company:
        company_upper = attendee_company.upper()
        font_company = adjust_font_size(c, company_upper, max_text_width, initial_font_size=18)
        c.setFont("DejaVuSans-Bold", font_company)
        c.setFillColor(colors.HexColor("#005BAB"))
        y_company = y_first + font_first + 4
        c.drawCentredString(page_cx, y_company, company_upper)
        c.setFillColor(colors.black)  # reset to black for subsequent content

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

def save_qr_code_svg(url, output_file):
    svg_buffer = generate_qr_code_svg(url)
    with open(output_file, 'wb') as f:
        f.write(svg_buffer.getvalue())

def main(qr_data, output_pdf):
    template_pdf = os.getenv("TEMPLATE_PDF")
    position_str = os.getenv("POSITION")
    qr_size = int(os.getenv("QR_SIZE"))  # Convert qr_size to integer
    position = tuple(map(int, position_str.split(',')))

    # Define the delete_temp_files variable
    delete_temp_files = True

    add_qr_to_pdf_template(template_pdf, output_pdf, qr_data, position, qr_size, delete_temp_files)

# Ejemplo de uso
if __name__ == "__main__":
    url = "https://globalai-madrid-2025.sessionize.com/"
    output_file = "qr_code.svg"
    save_qr_code_svg(url, output_file)
    print(f"QR code SVG saved to {output_file}")
