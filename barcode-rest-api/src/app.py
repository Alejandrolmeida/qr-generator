#!/usr/bin/env python3

from flask import Flask
from src.routes import register_routes

app = Flask(__name__)

# Middleware can be added here

register_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)