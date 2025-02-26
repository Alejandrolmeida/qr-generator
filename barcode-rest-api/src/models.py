class BarcodeData:
    def __init__(self, barcode, name):
        self.barcode = barcode
        self.name = name

    def validate(self):
        if not self.barcode.isdigit():
            raise ValueError("Barcode must contain only numbers.")
        if not self.name:
            raise ValueError("Name cannot be empty.")