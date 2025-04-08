from flask import Blueprint, request, jsonify
from models import BarcodeData

bp = Blueprint('api', __name__)

@bp.route('/barcode', methods=['POST'])
def add_barcode():
    data = request.get_json()
    barcode = data.get('barcode')
    name = data.get('name')

    if not barcode or not name or not barcode.isdigit():
        return jsonify({'error': 'Invalid input'}), 400

    barcode_data = BarcodeData(barcode=barcode, name=name)
    
    # Importar la función de forma local para evitar la dependencia circular
    from database import save_to_database
    if save_to_database(barcode_data):
        return jsonify({'message': 'Data saved successfully'}), 201
    else:
        return jsonify({'error': 'Failed to save data'}), 500

def register_routes(app):
    @app.route("/save", methods=["POST"])
    def save():
        # Importar la función de forma local para evitar la dependencia circular
        from database import save_to_database
        
        data = request.get_json()
        barcode = data.get("barcode")
        name = data.get("name")
        
        save_to_database(barcode, name)
        return jsonify({"message": "Item saved"}), 200