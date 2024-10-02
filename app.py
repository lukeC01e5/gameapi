import os
from flask import Flask, Response, render_template, request, jsonify, make_response, send_from_directory
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask_pymongo import PyMongo
from flask.json import JSONEncoder
from flask_cors import CORS
import logging

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

load_dotenv()

app = Flask(__name__, static_folder='static')
app.json_encoder = CustomJSONEncoder
CORS(app)

app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb+srv://colesluke:WZAQsanRtoyhuH6C@qrcluster.zxgcrnk.mongodb.net/playerData?retryWrites=true&w=majority&appName=qrCluster")

mongo = PyMongo(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# Login route
@app.route('/api/v1/login', methods=['POST'])
def login():
    try:
        username = request.json.get('username')
        password = request.json.get('password')

        app.logger.debug(f"Login attempt with username: {username}")

        if not username or not password:
            app.logger.error("Username and password are required")
            return make_response(jsonify({"error": "Username and password are required"}), 400)

        user_data = mongo.db.Users.find_one({"username": username, "password": password})

        if user_data:
            app.logger.debug(f"User authenticated: {user_data}")
            return jsonify(user_data)
        else:
            app.logger.error("Invalid username or password")
            return make_response(jsonify({"error": "Invalid username or password"}), 401)
    except Exception as e:
        app.logger.error(f"Error during login: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 500)

# Account creation route
@app.route('/api/v1/create_account', methods=['POST'])
def create_account():
    try:
        username = request.json.get('username')
        password = request.json.get('password')
        classroom = request.json.get('classroom')

        app.logger.debug(f"Account creation attempt with username: {username}, classroom: {classroom}")

        if not username or not password:
            app.logger.error("Username and password are required")
            return make_response(jsonify({"error": "Username and password are required"}), 400)

        existing_user = mongo.db.Users.find_one({"username": username})

        if existing_user:
            app.logger.error("Username already taken")
            return make_response(jsonify({"error": "Username already taken"}), 409)
        else:
            mongo.db.Users.insert_one({
                "username": username,
                "password": password,
                "classroom": classroom,
                "coin": 0,
                "meat": 0,
                "plant": 0,
                "crystal": 0,
                "water": 0
            })

            app.logger.debug("Account created successfully")
            return jsonify({"message": "Account created successfully"})
    except Exception as e:
        app.logger.error(f"Error during account creation: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 500)

# Add item routes
@app.route('/api/v1/users/<username>/add_coin', methods=['POST'])
def add_coin(username):
    return add_item(username, "coin")

@app.route('/api/v1/users/<username>/add_meat', methods=['POST'])
def add_meat(username):
    return add_item(username, "meat")

@app.route('/api/v1/users/<username>/add_plant', methods=['POST'])
def add_plant(username):
    return add_item(username, "plant")

@app.route('/api/v1/users/<username>/add_crystal', methods=['POST'])
def add_crystal(username):
    return add_item(username, "crystal")

@app.route('/api/v1/users/<username>/add_water', methods=['POST'])
def add_water(username):
    return add_item(username, "water")

def add_item(username, item):
    try:
        app.logger.debug(f"Adding {item} to user: {username}")
        result = mongo.db.Users.update_one({"username": username}, {"$inc": {item: 1}})

        if result.modified_count == 0:
            app.logger.error("No user found with given username")
            return jsonify({"error": "No user found with given username"}), 404

        app.logger.debug(f"1 {item} added successfully")
        return jsonify({"message": f"1 {item} added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding {item} to user: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Add creature routes
@app.route('/api/v1/users/<username>/add_babyDragon', methods=['POST'])
def add_babyDragon(username):
    return add_creature(username, "babyDragon")

@app.route('/api/v1/users/<username>/add_dinoEgg', methods=['POST'])
def add_dinoEgg(username):
    return add_creature(username, "dinoEgg")

@app.route('/api/v1/users/<username>/add_wolfPup', methods=['POST'])
def add_wolfPup(username):
    return add_creature(username, "wolfPup")

@app.route('/api/v1/users/<username>/add_kitten', methods=['POST'])
def add_kitten(username):
    return add_creature(username, "kitten")

@app.route('/api/v1/users/<username>/add_chicky', methods=['POST'])
def add_chicky(username):
    return add_creature(username, "chicky")

@app.route('/api/v1/users/<username>/add_fishy', methods=['POST'])
def add_fishy(username):
    return add_creature(username, "fishy")

@app.route('/api/v1/users/<username>/add_squidy', methods=['POST'])
def add_squidy(username):
    return add_creature(username, "squidy")

@app.route('/api/v1/users/<username>/add_larve', methods=['POST'])
def add_larve(username):
    return add_creature(username, "larve")

@app.route('/api/v1/users/<username>/add_sprouty', methods=['POST'])
def add_sprouty(username):
    return add_creature(username, "sprouty")

@app.route('/api/v1/users/<username>/add_roboCrab', methods=['POST'])
def add_roboCrab(username):
    return add_creature(username, "roboCrab")

@app.route('/api/v1/users/<username>/add_ghost', methods=['POST'])
def add_ghost(username):
    return add_creature(username, "ghost")

def add_creature(username, creature):
    try:
        app.logger.debug(f"Adding {creature} to user: {username}")
        result = mongo.db.Users.update_one({"username": username}, {"$push": {"creatures": creature}})

        if result.modified_count == 0:
            app.logger.error("No user found with given username")
            return jsonify({"error": "No user found with given username"}), 404

        app.logger.debug(f"1 {creature} added successfully")
        return jsonify({"message": f"1 {creature} added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding {creature} to user: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Get users route
@app.route('/api/v1/users', methods=['GET'])
def get_users():
    try:
        users = mongo.db.Users.find()
        users_list = list(users)
        return jsonify(users_list), 200
    except Exception as e:
        app.logger.error(f"Error fetching users: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Error handlers
@app.errorhandler(400)
def handle_400_error(error):
    return make_response(jsonify({
        "errorCode": error.code,
        "errorDescription": "Bad request!",
        "errorDetailedDescription": error.description,
        "errorName": error.name
    }), 400)

@app.errorhandler(404)
def handle_404_error(error):
    return make_response(jsonify({
        "errorCode": error.code,
        "errorDescription": "Resource not found!",
        "errorDetailedDescription": error.description,
        "errorName": error.name
    }), 404)

@app.errorhandler(500)
def handle_500_error(error):
    return make_response(jsonify({
        "errorCode": error.code,
        "errorDescription": "Internal Server Error",
        "errorDetailedDescription": error.description,
        "errorName": error.name
    }), 500)

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(str(e))
    return make_response(jsonify({
        "errorCode": 500,
        "errorDescription": "Internal Server Error",
        "errorDetailedDescription": str(e),
        "errorName": "Internal Server Error"
    }), 500)

if __name__ == "__main__":
    app.run(debug=True)