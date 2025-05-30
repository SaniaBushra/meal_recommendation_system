from flask import Flask, request, jsonify, session
from flask_cors import CORS
import json
import os
import uuid
from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')
# Configure session cookie for secure cross-site usage with credentials
app.config['SESSION_COOKIE_SAMESITE'] = 'None'  # Allow cross-site cookies
app.config['SESSION_COOKIE_SECURE'] = True      # Ensure cookies are sent over HTTPS only
app.config['SESSION_TYPE'] = 'filesystem'
# Enable CORS for all origins with credentials support for secure communication (development only)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

USERS_FILE = "users.json"
FEEDBACK_FILE = "feedback.json"


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def load_feedback():
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_feedback(feedback_list):
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(feedback_list, f, indent=2)


@app.route("/")
def home():
    return "Meal Recommendation System Backend is running."


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Missing username or password"}), 400

    users = load_users()

    if username not in users:
        return jsonify({"success": False, "message": "User not found. Please register first."}), 404

    if not check_password_hash(users[username]["password"], password):
        return jsonify({"success": False, "message": "Invalid password"}), 401

    session_id = str(uuid.uuid4())
    session["session_id"] = session_id
    session["username"] = username

    return jsonify({"success": True, "message": "Login successful", "session_id": session_id})


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    food_preference = data.get("food_preference")
    country = data.get("country")
    age = data.get("age")

    if not all([username, password, food_preference, country, age]):
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    users = load_users()

    if username in users:
        return jsonify({"success": False, "message": "Username already exists"}), 409

    users[username] = {
        "password": generate_password_hash(password),
        "food_preference": food_preference,
        "country": country,
        "age": age,
        "created_at": datetime.utcnow().isoformat()
    }
    save_users(users)

    return jsonify({"success": True, "message": "Registration successful"})


@app.route("/profile", methods=["GET"])
def profile():
    session_id = session.get("session_id")
    username = session.get("username")

    if not session_id or not username:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    try:
        with open("backend/meals.json", "r") as f:
            meals = json.load(f)
    except Exception as e:
        print(f"Error loading meals dataset: {e}")
        meals = []

    now = datetime.utcnow()
    hour = now.hour

    if 5 <= hour < 11:
        meal_time = "breakfast"
    elif 11 <= hour < 16:
        meal_time = "lunch"
    elif 16 <= hour < 19:
        meal_time = "snack"
    elif 19 <= hour < 23:
        meal_time = "dinner"
    else:
        meal_time = "snack"
        

    filtered_meals = [meal for meal in meals if meal["type"] == user["food_preference"].lower() and meal["meal"] == meal_time]

    import random
    recommendation = random.choice(filtered_meals) if filtered_meals else None

    profile_data = {
        "username": username,
        "country": user["country"],
        "age": user["age"],
        "food_preference": user["food_preference"],
        "recommendation": recommendation
    }

    return jsonify({"success": True, "profile": profile_data})

@app.route("/profile", methods=["POST"])
def update_profile():
    session_id = session.get("session_id")
    username = session.get("username")

    if not session_id or not username:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.json
    new_food_preference = data.get("food_preference")

    if not new_food_preference or new_food_preference.lower() not in ["veg", "non-veg"]:
        return jsonify({"success": False, "message": "Invalid food preference"}), 400

    users = load_users()
    user = users.get(username)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    user["food_preference"] = new_food_preference.lower()
    users[username] = user
    save_users(users)

    return jsonify({"success": True, "message": "Food preference updated"})


@app.route("/recommendation", methods=["POST"])
def recommendation():
    data = request.json
    username = data.get("username")
    food_type = data.get("food_type")
    meal_type = data.get("meal_type")

    if not username or not food_type or not meal_type:
        return jsonify({"error": "Missing username, food_type or meal_type"}), 400

    try:
        with open("backend/meals.json", "r") as f:
            meals = json.load(f)
    except Exception as e:
        print(f"Error loading meals dataset: {e}")
        meals = []

    feedback_list = load_feedback()
    disliked_meal_ids = set()
    for fb in feedback_list:
        if fb.get("username") == username and fb.get("liked") == False:
            try:
                disliked_meal_ids.add(int(fb["meal_id"]))
            except Exception:
                continue

    filtered_meals = []
    for meal in meals:
        if meal["type"].lower() == food_type.lower() and meal_type.lower() == meal["meal"].lower() and meal["id"] not in disliked_meal_ids:
            filtered_meals.append(meal)

    if not filtered_meals:
        return jsonify({"error": "No meals found for the given criteria"}), 404

    import random
    recommendation = random.choice(filtered_meals)

    return jsonify({
        "recommendation": {
            "id": recommendation.get("id"),
            "name": recommendation.get("name"),
            "restaurant_name": recommendation.get("restaurant_name"),
            "meal": recommendation.get("meal")
        }
    })


@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    username = data.get("username")
    meal_id = data.get("meal_id")
    liked = data.get("liked")

    if not username or meal_id is None or liked is None:
        return jsonify({"error": "Missing username, meal_id or liked"}), 400

    feedback_list = load_feedback()
    # Ensure username is saved in feedback entries
    feedback_list.append({"username": username, "meal_id": meal_id, "liked": liked})
    save_feedback(feedback_list)

    return jsonify({"success": True, "message": "Feedback saved"})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
