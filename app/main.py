import os
from flask import Flask, jsonify

app = os.environ.get("APP_NAME", "Luncher API")
server = Flask(__name__)

@server.route("/")
def home():
    return jsonify({
        "status": "healthy",
        "app": app,
        "description": "Welcome to Luncher! The ultimate team lunch coordination service.",
        "version": "1.0.0"
    })

@server.route("/lunches")
def get_lunches():
    return jsonify([
        {"id": 1, "name": "Antigravity Burger Joint", "cuisine": "Burgers", "rating": 4.9},
        {"id": 2, "name": "Vibrant Salad Bar", "cuisine": "Healthy", "rating": 4.7},
        {"id": 3, "name": "Taco Time", "cuisine": "Mexican", "rating": 4.8},
        {"id": 4, "name": "Noodle Nest", "cuisine": "Asian", "rating": 4.6}
    ])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)
