from flask import Flask
from routes import register_routes

app = Flask(__name__)

# Middleware can be added here

register_routes(app)

if __name__ == "__main__":
    app.run(debug=True)