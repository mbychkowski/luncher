import os
import uuid
from flask import Flask, jsonify, request

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

@server.route("/catering", methods=["GET"])
def get_catering():
    return jsonify([
        {
            "id": 1,
            "vendor": "Vibrant Salad Bar",
            "cuisine": "Healthy",
            "rating": 4.7,
            "menu": [
                {"name": "Gluten-free Falafel bowl", "price": 14.50, "dietary": ["Gluten-Free", "Vegetarian", "Vegan"]},
                {"name": "Vegetarian Quinoa salad", "price": 12.99, "dietary": ["Vegetarian", "Gluten-Free"]},
                {"name": "Avocado Cobb Salad", "price": 15.50, "dietary": []}
            ]
        },
        {
            "id": 2,
            "vendor": "Antigravity Burger Joint",
            "cuisine": "Burgers",
            "rating": 4.9,
            "menu": [
                {"name": "Classic Cheeseburger", "price": 12.99, "dietary": []},
                {"name": "Vegan Beyond Burger", "price": 14.99, "dietary": ["Vegetarian", "Vegan"]},
                {"name": "Gluten-free Bacon Burger", "price": 15.50, "dietary": ["Gluten-Free"]}
            ]
        },
        {
            "id": 3,
            "vendor": "Noodle Nest",
            "cuisine": "Asian",
            "rating": 4.6,
            "menu": [
                {"name": "Spicy Tofu Ramen", "price": 13.99, "dietary": ["Vegetarian", "Vegan"]},
                {"name": "Chicken Teriyaki Bento", "price": 16.50, "dietary": []},
                {"name": "Gluten-free Rice Noodles", "price": 14.99, "dietary": ["Gluten-Free", "Vegetarian"]}
            ]
        }
    ])

@server.route("/calendar", methods=["GET"])
def get_calendar():
    # Simulated calendar busy blocks for team members
    # Target meeting is 90 minutes. Normal work day is 09:00 - 17:00.
    return jsonify({
        "Alice": [
            {"start": "09:00", "end": "11:30", "status": "busy"},
            {"start": "13:30", "end": "17:00", "status": "busy"}
        ],
        "Bob": [
            {"start": "10:00", "end": "12:00", "status": "busy"},
            {"start": "14:00", "end": "16:00", "status": "busy"}
        ],
        "Charlie": [
            {"start": "11:00", "end": "12:30", "status": "busy"},
            {"start": "15:00", "end": "17:00", "status": "busy"}
        ],
        "David": [
            {"start": "09:00", "end": "10:30", "status": "busy"},
            {"start": "13:00", "end": "15:00", "status": "busy"}
        ]
    })

@server.route("/orders", methods=["POST"])
def place_order():
    data = request.json or {}
    restaurant = data.get("restaurant")
    items = data.get("items", [])
    total_cost = data.get("total_cost", 0.0)
    
    if not restaurant or not items:
        return jsonify({"error": "Missing restaurant or items in order payload."}), 400
        
    order_id = f"LCH-{uuid.uuid4().hex[:6].upper()}"
    return jsonify({
        "status": "success",
        "order_id": order_id,
        "message": f"Draft catering order placed successfully with {restaurant}.",
        "restaurant": restaurant,
        "items": items,
        "total_cost": total_cost
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server.run(host="0.0.0.0", port=port)
