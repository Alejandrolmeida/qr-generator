from flask import Blueprint, request, jsonify
from models import BarcodeData
from database import save_to_database

bp = Blueprint('api', __name__)

@bp.route('/barcode', methods=['POST'])
def add_barcode():
    data = request.get_json()
    barcode = data.get('barcode')
    name = data.get('name')

    if not barcode or not name or not barcode.isdigit():
        return jsonify({'error': 'Invalid input'}), 400

    barcode_data = BarcodeData(barcode=barcode, name=name)
    
    if save_to_database(barcode_data):
        return jsonify({'message': 'Data saved successfully'}), 201
    else:
        return jsonify({'error': 'Failed to save data'}), 500