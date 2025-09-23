#latest version trying to add coin to user value
#trying to change to the new version with two rfid blocks

import os
from flask import Flask, Response, render_template, request, jsonify, make_response
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask_pymongo import PyMongo
from flask.json import JSONEncoder
from flask_cors import CORS
from flask import send_from_directory
from functools import wraps


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

load_dotenv()

app = Flask(__name__)
app.json_encoder = CustomJSONEncoder

# Updated CORS to allow both your website and ESP32
CORS(app, origins=[
    'https://lootbox-portal-a7b5db61cb5f.herokuapp.com',  # Your production frontend
    'http://localhost:3000',  # Your local development
    'https://localhost:3000',   # Local HTTPS if needed
    'http://127.0.0.1:5000',
    'https://gameapi-2e9bb6e38339.herokuapp.com'  # Added your API domain
])


app.config["MONGO_URI"] = "mongodb+srv://colesluke:WZAQsanRtoyhuH6C@qrcluster.zxgcrnk.mongodb.net/playerData?retryWrites=true&w=majority&appName=qrCluster"

mongo = PyMongo(app)

# Modified API key decorator to be optional
def require_api_key_optional(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.getenv('API_KEY')
        
        # If API key is provided, validate it
        if api_key:
            if api_key != expected_key:
                return make_response(jsonify({"error": "Invalid API key"}), 401)
        
        # If no API key provided, continue (for website requests)
        return f(*args, **kwargs)
    return decorated_function

# Strict API key requirement (for sensitive operations)
def require_api_key_strict(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.getenv('API_KEY')
        
        if not api_key or api_key != expected_key:
            return make_response(jsonify({"error": "API key required"}), 401)
        
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    return render_template("index.html")

# ESP32 endpoints - require API key
@app.route("/api/v1/add_5_coin", methods=["POST"])
@require_api_key_strict
def add_5_coin():
    try:
        # Expecting a JSON body with "rfidUID"
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        rfid_uid = data.get("rfidUID")
        if not rfid_uid:
            return make_response(jsonify({"error": "rfidUID is required"}), 400)

        # Attempt to update the user's coins by +5 using rfidUID
        result = mongo.db.Users.update_one(
            {"rfidUID": rfid_uid},
            {"$inc": {"coins": 5}}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        return jsonify({"message": "5 coins added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding 5 coins: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/create_user_from_rfid", methods=["POST"])
@require_api_key_strict
def create_user_from_rfid():
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        name = data.get("name")
        password = data.get("password")
        rfidUID = data.get("rfidUID")
        playerClass = data.get("playerClass")
        mainCreature = data.get("mainCreature", "")
        challengeCodes = data.get("challengeCodes", [])
        creatures = data.get("creatures", [])
        artifacts = data.get("artifacts", [])
        loot = data.get("loot", [])  # Add this line for loot

        if not all([name, password, rfidUID, playerClass]):
            return make_response(jsonify({"error": "Missing required fields"}), 400)

        # Check if this RFID UID already exists
        existing_user = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if existing_user:
            # Return a warning, but still allow overwrite if client confirms
            return jsonify({
                "warning": True,
                "message": "Warning: This RFID tag is already assigned to another user. Submitting will overwrite existing data!"
            }), 200

        # If not exists, create new user
        user = {
            "name": name,
            "password": password,
            "rfidUID": rfidUID,
            "playerClass": playerClass,
            "mainCreature": mainCreature,
            "challengeCodes": challengeCodes,
            "creatures": creatures,
            "artifacts": artifacts,
            "loot": loot,  # Add this line
            "coins": 0     # Initialize coins to 0
        }

        result = mongo.db.Users.insert_one(user)

        return jsonify({
            "warning": False,
            "message": "User created successfully",
            "userId": str(result.inserted_id)
        }), 201

    except Exception as e:
        app.logger.error(f"Error creating user from RFID data: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

# Website endpoints - optional API key
@app.route("/api/v1/login", methods=["POST"])
@require_api_key_optional
def login_user():
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"warning": True, "message": "No data provided"}), 400)

        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            return make_response(jsonify({"warning": True, "message": "Username and password required"}), 400)

        user = mongo.db.Users.find_one({"name": username, "password": password})
        if not user:
            return make_response(jsonify({"warning": True, "message": "Invalid username or password"}), 401)

        user.pop("_id", None)
        user.pop("password", None)

        return jsonify({"warning": False, "user": user}), 200

    except Exception as e:
        app.logger.error(f"Error logging in: {str(e)}")
        return make_response(jsonify({"warning": True, "message": "Internal Server Error"}), 500)

# Public endpoints - no API key required
@app.route("/api/v1/get_custom_names", methods=["GET"])
def get_custom_names():
    try:
        # Retrieve only the 'customName' field from all documents
        users = mongo.db.Users.find({}, {"_id": 0, "name": 1})  # Changed from customName to name
        
        # Build a list of custom names
        custom_names = [user["name"] for user in users if "name" in user]
        
        return jsonify(custom_names), 200
    except Exception as e:
        app.logger.error(f"Error fetching custom names: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

# FIXED: Single users endpoint that handles both ESP32 and website requests
@app.route('/api/v1/users', methods=['GET'])
@require_api_key_optional
def get_users():
    try:
        # Check if this is an ESP32 request for a specific user
        rfid_uid = request.args.get("rfidUID")
        if rfid_uid:
            # ESP32 request - get specific user by RFID with only name
            user = mongo.db.Users.find_one({"rfidUID": rfid_uid}, {"_id": 0, "name": 1})
            if not user:
                return make_response(jsonify({"error": "No user found for the given rfidUID"}), 404)
            return jsonify({"playerName": user["name"]}), 200
        else:
            # Website request - get all users (without sensitive data)
            users = mongo.db.Users.find({}, {"_id": 0, "name": 1, "playerClass": 1, "coins": 1, "creatures": 1, "artifacts": 1, "loot": 1})
            users_list = list(users)
            return jsonify(users_list), 200
    except Exception as e:
        app.logger.error(f"Error fetching users: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ESP32 specific endpoints
@app.route("/api/v1/users/<rfidUID>/add_creature", methods=["POST"])
@require_api_key_strict
def add_creature(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        # For example, we expect JSON like:
        # {
        #   "creatureName": "Dragon",
        #   "creatureValue": 7
        # }
        creature_name = data.get("creatureName")
        creature_value = data.get("creatureValue")

        if creature_name is None or creature_value is None:
            return make_response(jsonify({"error": "Missing creatureName or creatureValue"}), 400)

        # Push the creature to the "creatures" list in the user's document
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {"$push": {"creatures": {"name": creature_name, "value": creature_value}}}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        return jsonify({"message": "Creature added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding creature: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/users/<rfidUID>/add_artifact", methods=["POST"])
@require_api_key_strict
def add_artifact(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        # For example, we expect:
        # {
        #   "artifactName": "Ancient Amulet",
        #   "artifactPower": 12
        # }
        artifact_name = data.get("artifactName")
        artifact_power = data.get("artifactPower")

        if artifact_name is None or artifact_power is None:
            return make_response(jsonify({"error": "Missing artifactName or artifactPower"}), 400)

        # Push the artifact to the "artifacts" list in the user's document
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {"$push": {"artifacts": {"name": artifact_name, "power": artifact_power}}}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        return jsonify({"message": "Artifact added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding artifact: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/users/<rfidUID>/add_challenge_code", methods=["POST"])
@require_api_key_strict
def add_challenge_code(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        # Expect JSON like:
        # {
        #   "challengeCode": 123,
        #   "digit": 7
        # }
        challenge_code = data.get("challengeCode")
        digit = data.get("digit")

        if (challenge_code is None or digit is None):
            return make_response(jsonify({"error": "Missing challengeCode or digit"}), 400)

        # Push the new item into the 'challengeCodes' array
        # Each entry could look like: {"code": 123, "digit": 7}
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {"$push": {"challengeCodes": {"code": challenge_code, "digit": digit}}}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        return jsonify({"message": "Challenge code added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding challenge code: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/update_creature_loot_and_coin", methods=["POST"])
@require_api_key_strict
def update_creature_loot_and_coin():
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        rfid_uid = data.get("rfidUID")
        add_coins = data.get("addCoins", 0)
        creatures = data.get("creatures", [])
        loot = data.get("loot", [])

        if not rfid_uid:
            return make_response(jsonify({"error": "rfidUID is required"}), 400)

        result = mongo.db.Users.update_one(
            {"rfidUID": rfid_uid},
            {
                "$inc": {"coins": add_coins},
                "$push": {
                    "creatures": {"$each": creatures},
                    "loot": {"$each": loot}
                }
            }
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for this rfidUID"}), 404)

        return jsonify({"message": "Creature, loot, and coins updated successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error updating creature, loot, and coins: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/users/<rfidUID>/set_main_creature", methods=["POST"])
@require_api_key_optional
def set_main_creature(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        creature_name = data.get("creatureName")
        if not creature_name:
            return make_response(jsonify({"error": "creatureName is required"}), 400)

        # Update the main creature and ensure the creature has stats
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID, "creatures.name": creature_name},
            {
                "$set": {
                    "mainCreature": creature_name,
                    "creatures.$.stats": {
                        "power": data.get("power", 3),
                        "defence": data.get("defence", 3),
                        "speed": data.get("speed", 3)
                    }
                }
            }
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Creature not found or user not found"}), 404)

        return jsonify({"message": "Main creature updated successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error setting main creature: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/users/<rfidUID>/update_creature_stats", methods=["POST"])
@require_api_key_optional
def update_creature_stats(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        creature_name = data.get("creatureName")
        stats = data.get("stats", {})
        
        if not creature_name:
            return make_response(jsonify({"error": "creatureName is required"}), 400)

        # Update the creature's stats
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID, "creatures.name": creature_name},
            {"$set": {"creatures.$.stats": stats}}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Creature not found or user not found"}), 404)

        return jsonify({"message": "Creature stats updated successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error updating creature stats: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/complete_loot_upload", methods=["POST"])
@require_api_key_strict
def complete_loot_upload():
    try:
        data = request.json
        rfid_uid = data.get('rfidUID')
        add_coins = data.get('addCoins', 0)
        creatures = data.get('creatures', [])
        loot = data.get('loot', [])
        
        user = mongo.db.Users.find_one({"rfidUID": rfid_uid})
        if not user:
            return make_response(jsonify({"error": "User not found"}), 404)
        
        result = mongo.db.Users.update_one(
            {"rfidUID": rfid_uid},
            {
                "$inc": {"coins": add_coins},
                "$push": {
                    "creatures": {"$each": creatures},
                    "loot": {"$each": loot}
                }
            }
        )
        
        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for this rfidUID"}), 404)
        
        updated_user = mongo.db.Users.find_one({"rfidUID": rfid_uid})
        
        app.logger.info(f"Complete loot upload for user {user['name']}: +{add_coins} coins, {len(creatures)} creatures, {len(loot)} loot")
        return make_response(jsonify({
            "message": "Upload successful",
            "coinsAdded": add_coins,
            "creaturesAdded": len(creatures),
            "lootAdded": len(loot),
            "totalCoins": updated_user.get("coins", 0)
        }), 200)
        
    except Exception as e:
        app.logger.error(f"Error in complete loot upload: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/debug/users", methods=["GET"])
@require_api_key_strict
def debug_users():
    try:
        # Get all users to see what's in the database
        users = list(mongo.db.Users.find({}, {"_id": 0, "name": 1, "rfidUID": 1}))
        return jsonify({
            "total_users": len(users),
            "users": users
        })
    except Exception as e:
        app.logger.error(f"Error in debug_users: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 500)

# Error handlers
@app.errorhandler(400)
def handle_400_error(error):
    return make_response(jsonify({"errorCode": error.code, 
                                  "errorDescription": "Bad request!",
                                  "errorDetailedDescription": error.description,
                                  "errorName": error.name}), 400)

@app.errorhandler(404)
def handle_404_error(error):
    return make_response(jsonify({"errorCode": error.code, 
                                  "errorDescription": "Resource not found!",
                                  "errorDetailedDescription": error.description,
                                  "errorName": error.name}), 404)

@app.errorhandler(500)
def handle_500_error(error):
    return make_response(jsonify({"errorCode": error.code, 
                                  "errorDescription": "Internal Server Error",
                                  "errorDetailedDescription": error.description,
                                  "errorName": error.name}), 500) 
    
@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(str(e))
    return make_response(jsonify({"errorCode": 500, 
                                  "errorDescription": "Internal Server Error",
                                  "errorDetailedDescription": str(e),
                                  "errorName": "Internal Server Error"}), 500)

@app.route("/api/v1/users/<rfidUID>/add_crafted_artifact", methods=["POST"])
def add_crafted_artifact(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        artifact_name = data.get("name")
        artifact_power = data.get("power")
        artifact_emoji = data.get("emoji")
        artifact_type = data.get("type", "crafted")

        if not artifact_name or artifact_power is None:
            return make_response(jsonify({"error": "Missing artifact name or power"}), 400)

        # Create the artifact object
        crafted_artifact = {
            "name": artifact_name,
            "power": artifact_power,
            "emoji": artifact_emoji,
            "type": artifact_type
        }

        # Push the artifact to the "artifacts" list in the user's document
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {"$push": {"artifacts": crafted_artifact}}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        return jsonify({"message": "Crafted artifact added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding crafted artifact: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

if __name__ == "__main__":
    app.run(debug=True)



