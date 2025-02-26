import unittest
from src.app import app

class TestBarcodeAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_post_barcode(self):
        response = self.app.post('/api/barcode', json={
            'barcode': '123456789012',
            'name': 'Test Name'
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn('data saved', response.get_data(as_text=True))

    def test_post_invalid_barcode(self):
        response = self.app.post('/api/barcode', json={
            'barcode': 'invalid_barcode',
            'name': 'Test Name'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid barcode', response.get_data(as_text=True))

    def test_post_missing_name(self):
        response = self.app.post('/api/barcode', json={
            'barcode': '123456789012'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('Name is required', response.get_data(as_text=True))

if __name__ == '__main__':
    unittest.main()