# Barcode REST API

This project is a simple REST API built with Flask that allows users to submit a barcode (numeric only) and a name. The submitted data is then stored in a Cosmos DB database.

## Project Structure

```
barcode-rest-api
├── src
│   ├── app.py          # Entry point of the application
│   ├── routes.py       # API routes definition
│   ├── models.py       # Data model for barcode and name
│   └── database.py     # Database connection and CRUD operations
├── tests
│   └── test_app.py     # Unit tests for the application
├── requirements.txt     # Project dependencies
└── README.md            # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd barcode-rest-api
   ```

2. **Create a virtual environment:**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Set up Cosmos DB:**
   - Create a Cosmos DB account and a database.
   - Update the connection details in `src/database.py`.

5. **Run the application:**
   ```
   python src/app.py
   ```

## API Usage

### POST /api/barcode

- **Request Body:**
  ```json
  {
    "barcode": "123456789012",
    "name": "Sample Name"
  }
  ```

- **Response:**
  - **Success (201 Created):**
    ```json
    {
      "message": "Data saved successfully."
    }
    ```
  - **Error (400 Bad Request):**
    ```json
    {
      "error": "Invalid input."
    }
    ```

## Running Tests

To run the unit tests, use the following command:

```
pytest tests/test_app.py
```

## License

This project is licensed under the MIT License.