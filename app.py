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
import os
import datetime
import traceback


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

load_dotenv()

app = Flask(__name__)
app.json_encoder = CustomJSONEncoder

# Updated CORS to allow both your website and ESP32
CORS(app, 
     origins=[
         'https://lootbox-portal-a7b5db61cb5f.herokuapp.com',
         'http://localhost:3000',
         'https://localhost:3000',
         'http://127.0.0.1:5000',
         'https://gameapi-2e9bb6e38339.herokuapp.com'
     ],
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization', 'X-API-Key', 'X-Teacher-Token'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
)


app.config["MONGO_URI"] = os.getenv('MONGO_URI')

mongo = PyMongo(app)


# ==========================================
# TEACHER ENDPOINTS (NEW)
# ==========================================

def require_api_key_optional(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ✅ Allow OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return make_response('', 204)
            
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
        # ✅ Allow OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return make_response('', 204)
            
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
        }, 201)

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
        # Check if this is a request for a specific user by RFID
        rfid_uid = request.args.get("rfidUID")
        if rfid_uid:
            # Get specific user with ALL data including challengeCodes
            user = mongo.db.Users.find_one(
                {"rfidUID": rfid_uid},
                {"_id": 0, "password": 0}  # Exclude only sensitive fields
            )
            if not user:
                return make_response(jsonify({"error": "No user found for the given rfidUID"}), 404)
            return jsonify(user), 200
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

        # First, check if user exists
        user = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if not user:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        # Update just the main creature (don't require creature to exist in collection)
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {"$set": {"mainCreature": creature_name}}
        )

        # If the creature exists in the user's collection, update its stats
        creature_exists = mongo.db.Users.find_one(
            {"rfidUID": rfidUID, "creatures.name": creature_name}
        )
        
        if creature_exists:
            # Update existing creature stats
            mongo.db.Users.update_one(
                {"rfidUID": rfidUID, "creatures.name": creature_name},
                {
                    "$set": {
                        "creatures.$.stats": {
                            "power": data.get("power", 3),
                            "defence": data.get("defence", 3),
                            "speed": data.get("speed", 3)
                        }
                    }
                }
            )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Failed to update main creature"}), 500)

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
@require_api_key_optional  # <-- Add this line
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

# Add this new endpoint for adding creatures with stacking
@app.route("/api/v1/users/<rfidUID>/add_creature_stacked", methods=["POST"])
@require_api_key_strict
def add_creature_stacked(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        creature_name = data.get("creatureName")
        creature_value = data.get("creatureValue", 1)
        count_to_add = data.get("count", 1)

        if not creature_name:
            return make_response(jsonify({"error": "Missing creatureName"}), 400)

        # Check if creature already exists in user's collection
        user = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if not user:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        # Find existing creature
        existing_creature = None
        for i, creature in enumerate(user.get("creatures", [])):
            if creature.get("name") == creature_name:
                existing_creature = {"creature": creature, "index": i}
                break

        if existing_creature:
            # Increment existing creature count
            result = mongo.db.Users.update_one(
                {"rfidUID": rfidUID, "creatures.name": creature_name},
                {"$inc": {"creatures.$.count": count_to_add}}
            )
        else:
            # Add new creature with count
            new_creature = {
                "name": creature_name,
                "value": creature_value,
                "count": count_to_add
            }
            result = mongo.db.Users.update_one(
                {"rfidUID": rfidUID},
                {"$push": {"creatures": new_creature}}
            )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Failed to update creature"}), 500)

        return jsonify({"message": f"Added {count_to_add} {creature_name}(s) successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding stacked creature: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

# Add this new endpoint for adding loot/resources with stacking
@app.route("/api/v1/users/<rfidUID>/add_loot_stacked", methods=["POST"])
@require_api_key_strict
def add_loot_stacked(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        loot_name = data.get("lootName")
        count_to_add = data.get("count", 1)

        if not loot_name:
            return make_response(jsonify({"error": "Missing lootName"}), 400)

        # Check if loot already exists in user's collection
        user = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if not user:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        # Find existing loot
        existing_loot = None
        for i, loot in enumerate(user.get("loot", [])):
            if loot.get("name") == loot_name:
                existing_loot = {"loot": loot, "index": i}
                break

        if existing_loot:
            # Increment existing loot count
            result = mongo.db.Users.update_one(
                {"rfidUID": rfidUID, "loot.name": loot_name},
                {"$inc": {"loot.$.count": count_to_add}}
            )
        else:
            # Add new loot with count
            new_loot = {
                "name": loot_name,
                "count": count_to_add,
                "type": "loot"
            }
            result = mongo.db.Users.update_one(
                {"rfidUID": rfidUID},
                {"$push": {"loot": new_loot}}
            )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Failed to update loot"}), 500)

        return jsonify({"message": f"Added {count_to_add} {loot_name}(s) successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding stacked loot: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

# Update the complete loot upload endpoint to handle stacking
@app.route("/api/v1/complete_loot_upload_stacked", methods=["POST"])
@require_api_key_strict
def complete_loot_upload_stacked():
    try:
        data = request.json
        app.logger.info(f"[complete_loot_upload_stacked] Received data: {data}")
        
        rfid_uid = data.get('rfidUID')
        add_coins = data.get('addCoins', 0)
        creatures = data.get('creatures', [])
        loot = data.get('loot', [])
        
        app.logger.info(f"[complete_loot_upload_stacked] Processing - RFID: {rfid_uid}, Coins: {add_coins}")
        app.logger.info(f"[complete_loot_upload_stacked] Creatures: {creatures}")
        app.logger.info(f"[complete_loot_upload_stacked] Loot: {loot}")
        
        user = mongo.db.Users.find_one({"rfidUID": rfid_uid})
        if not user:
            app.logger.error(f"[complete_loot_upload_stacked] User not found for RFID: {rfid_uid}")
            return make_response(jsonify({"error": "User not found"}), 404)
        
        app.logger.info(f"[complete_loot_upload_stacked] Found user: {user['name']}")
        
        creatures_processed = 0
        loot_processed = 0
        
        # Process creatures with stacking
        for creature_data in creatures:
            creature_name = creature_data.get("name")
            creature_value = creature_data.get("value", 1)
            count = creature_data.get("count", 1)
            
            app.logger.info(f"[complete_loot_upload_stacked] Processing creature: {creature_name}, value: {creature_value}, count: {count}")
            
            if not creature_name:
                app.logger.warning(f"[complete_loot_upload_stacked] Skipping creature with no name: {creature_data}")
                continue
                
            # Check if creature already exists
            existing_creature = mongo.db.Users.find_one(
                {"rfidUID": rfid_uid, "creatures.name": creature_name}
            )
            
            if existing_creature:
                app.logger.info(f"[complete_loot_upload_stacked] Incrementing existing creature {creature_name} by {count}")
                # Increment count
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid, "creatures.name": creature_name},
                    {"$inc": {"creatures.$.count": count}}
                )
                app.logger.info(f"[complete_loot_upload_stacked] Creature increment result: {result.modified_count}")
            else:
                app.logger.info(f"[complete_loot_upload_stacked] Adding new creature {creature_name} with count {count}")
                # Add new creature
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid},
                    {"$push": {"creatures": {
                        "name": creature_name,
                        "value": creature_value,
                        "count": count
                    }}}
                )
                app.logger.info(f"[complete_loot_upload_stacked] New creature result: {result.modified_count}")
            
            creatures_processed += 1
        
        # Process loot with stacking
        for loot_data in loot:
            loot_name = loot_data.get("name")
            count = loot_data.get("count", 1)
            
            app.logger.info(f"[complete_loot_upload_stacked] Processing loot: {loot_name}, count: {count}")
            
            if not loot_name:
                app.logger.warning(f"[complete_loot_upload_stacked] Skipping loot with no name: {loot_data}")
                continue
            
            # Check if loot already exists
            existing_loot = mongo.db.Users.find_one(
                {"rfidUID": rfid_uid, "loot.name": loot_name}
            )
            
            if existing_loot:
                app.logger.info(f"[complete_loot_upload_stacked] Incrementing existing loot {loot_name} by {count}")
                # Increment count
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid, "loot.name": loot_name},
                    {"$inc": {"loot.$.count": count}}
                )
                app.logger.info(f"[complete_loot_upload_stacked] Loot increment result: {result.modified_count}")
            else:
                app.logger.info(f"[complete_loot_upload_stacked] Adding new loot {loot_name} with count {count}")
                # Add new loot
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid},
                    {"$push": {"loot": {
                        "name": loot_name,
                        "count": count,
                        "type": "loot"
                    }}}
                )
                app.logger.info(f"[complete_loot_upload_stacked] New loot result: {result.modified_count}")
            
            loot_processed += 1
        
        # Add coins
        if add_coins > 0:
            app.logger.info(f"[complete_loot_upload_stacked] Adding {add_coins} coins")
            coin_result = mongo.db.Users.update_one(
                {"rfidUID": rfid_uid},
                {"$inc": {"coins": add_coins}}
            )
            app.logger.info(f"[complete_loot_upload_stacked] Coin update result: {coin_result.modified_count}")
        
        updated_user = mongo.db.Users.find_one({"rfidUID": rfid_uid})
        
        app.logger.info(f"[complete_loot_upload_stacked] FINAL RESULT - User: {user['name']}, Creatures processed: {creatures_processed}, Loot processed: {loot_processed}, Total coins: {updated_user.get('coins', 0)}")
        
        return make_response(jsonify({
            "message": "Stacked upload successful",
            "coinsAdded": add_coins,
            "creaturesProcessed": creatures_processed,
            "lootProcessed": loot_processed,
            "totalCoins": updated_user.get("coins", 0)
        }), 200)
        
    except Exception as e:
        app.logger.error(f"[complete_loot_upload_stacked] ERROR: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/users/<rfidUID>/set_main_creature_stacked", methods=["POST"])
@require_api_key_optional
def set_main_creature_stacked(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        creature_name = data.get("creatureName")
        if not creature_name:
            return make_response(jsonify({"error": "creatureName is required"}), 400)

        # First, check if user exists
        user = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if not user:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        # Set the main creature
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {"$set": {"mainCreature": creature_name}}
        )

        # Find the creature and decrement its count
        creature_exists = mongo.db.Users.find_one(
            {"rfidUID": rfidUID, "creatures.name": creature_name}
        )
        
        if creature_exists:
            # Find the specific creature in the array
            for creature in creature_exists.get("creatures", []):
                if creature.get("name") == creature_name:
                    current_count = creature.get("count", 1)
                    
                    if current_count > 1:
                        # Decrement count
                        mongo.db.Users.update_one(
                            {"rfidUID": rfidUID, "creatures.name": creature_name},
                            {"$inc": {"creatures.$.count": -1}}
                        )
                    else:
                        # Remove creature entirely if count would be 0
                        mongo.db.Users.update_one(
                            {"rfidUID": rfidUID},
                            {"$pull": {"creatures": {"name": creature_name}}}
                        )
                    break

        return jsonify({"message": "Main creature set and count decremented"}), 200

    except Exception as e:
        app.logger.error(f"Error setting main creature with stacking: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/test_stacked", methods=["POST"])
@require_api_key_strict
def test_stacked():
    try:
        data = request.json
        print(f"RECEIVED DATA: {data}")  # This will show in Heroku logs
        
        return jsonify({
            "message": "Test successful", 
            "received": data
        }), 200
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/v1/teachers/register", methods=["POST"])  # ✅ ADD THIS LINE
@require_api_key_optional
def register_teacher():
    """Register a new teacher account"""
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        school = data.get("school")

        if not all([name, email, password, school]):
            return make_response(jsonify({"error": "Missing required fields"}), 400)

        # Check if teacher email already exists
        existing_teacher = mongo.db.Teachers.find_one({"email": email})
        if existing_teacher:
            return make_response(jsonify({"error": "Email already registered"}), 409)

        # Create teacher document
        teacher = {
            "name": name,
            "email": email.lower(),  # Store emails in lowercase for consistency
            "password": password,  # In production, you'd hash this!
            "school": school,
            "classes": [],  # Will be populated with class IDs they manage
            "createdAt": datetime.datetime.utcnow()
        }

        result = mongo.db.Teachers.insert_one(teacher)

        app.logger.info(f"New teacher registered: {name} ({email})")

        return jsonify({
            "message": "Teacher account created successfully",
            "teacherId": str(result.inserted_id)
        }), 201

    except Exception as e:
        app.logger.error(f"Error registering teacher: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/teachers/login", methods=["POST"])
@require_api_key_optional
def login_teacher():
    """Authenticate teacher login"""
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return make_response(jsonify({"error": "Email and password required"}), 400)

        # Find teacher by email
        teacher = mongo.db.Teachers.find_one({"email": email.lower()})
        if not teacher:
            return make_response(jsonify({"error": "Invalid email or password"}), 401)

        # Verify password (in production, use hashed comparison)
        if teacher.get("password") != password:
            return make_response(jsonify({"error": "Invalid email or password"}), 401)

        # Generate simple token (in production, use JWT)
        teacher_id = str(teacher["_id"])
        token = f"teacher_{teacher_id}_{teacher['email']}"  # Simple token for now

        app.logger.info(f"Teacher logged in: {teacher['name']} ({email})")

        return jsonify({
            "message": "Login successful",
            "teacherId": teacher_id,
            "token": token,
            "name": teacher["name"],
            "school": teacher["school"]
        }), 200

    except Exception as e:
        app.logger.error(f"Error logging in teacher: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/teachers/<teacher_id>/classes", methods=["GET"])
@require_api_key_optional
def get_teacher_classes(teacher_id):
    """Get all classes for a teacher"""
    try:
        # Verify teacher exists
        teacher = mongo.db.Teachers.find_one({"_id": ObjectId(teacher_id)})
        if not teacher:
            return make_response(jsonify({"error": "Teacher not found"}), 404)

        # Get unique classes from their school
        # This finds all unique playerClass values from students in the same school
        pipeline = [
            {"$match": {"playerClass": {"$regex": f"^{teacher['school']}"}}},
            {"$group": {"_id": "$playerClass"}},
            {"$sort": {"_id": 1}}
        ]
        
        classes = list(mongo.db.Users.aggregate(pipeline))
        
        # Format classes for dropdown
        formatted_classes = []
        for cls in classes:
            class_name = cls["_id"]
            # Create ID by replacing spaces/slashes with hyphens
            class_id = class_name.replace(" / ", "-").replace(" ", "-")
            formatted_classes.append({
                "id": class_name,  # Use full name as ID for easier matching
                "name": class_name
            })

        # If no classes found, return default ones for that school
        if not formatted_classes:
            school_name = teacher['school'].split(' / ')[0]  # Get school name part
            formatted_classes = [
                {"id": f"{school_name} / Kowhai", "name": f"{school_name} / Kowhai"},
                {"id": f"{school_name} / Kauri", "name": f"{school_name} / Kauri"}
            ]

        return jsonify(formatted_classes), 200

    except Exception as e:
        app.logger.error(f"Error getting teacher classes: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/teachers/<teacher_id>/classes/<path:class_id>/students", methods=["GET"])
@require_api_key_optional
def get_class_students(teacher_id, class_id):
    """Get all students in a specific class"""
    try:
        # Verify teacher exists
        teacher = mongo.db.Teachers.find_one({"_id": ObjectId(teacher_id)})
        if not teacher:
            return make_response(jsonify({"error": "Teacher not found"}), 404)

        # Decode class_id (it comes URL-encoded)
        from urllib.parse import unquote
        class_name = unquote(class_id)

        # ✅ FIX: Include rfidUID in the response
        students = mongo.db.Users.find(
            {"playerClass": class_name},
            {"_id": 0, "name": 1, "coins": 1, "mainCreature": 1, "playerClass": 1, "creatures": 1, "artifacts": 1, "rfidUID": 1}  # ✅ Added rfidUID
        )

        students_list = []
        for student in students:
            students_list.append({
                "name": student.get("name", "Unknown"),
                "coins": student.get("coins", 0),
                "mainPet": student.get("mainCreature", "None"),
                "schoolClass": student.get("playerClass", class_name),
                "totalCreatures": len(student.get("creatures", [])),
                "totalArtifacts": len(student.get("artifacts", [])),
                "rfidUID": student.get("rfidUID", "")  # ✅ Added this line
            })

        # Sort by coins (leaderboard style)
        students_list.sort(key=lambda x: x["coins"], reverse=True)

        app.logger.info(f"Teacher {teacher['name']} viewing class {class_name}: {len(students_list)} students")

        return jsonify(students_list), 200

    except Exception as e:
        app.logger.error(f"Error getting class students: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


# Optional: Get teacher profile
@app.route("/api/v1/teachers/<teacher_id>", methods=["GET"])
@require_api_key_optional
def get_teacher_profile(teacher_id):
    """Get teacher profile information"""
    try:
        teacher = mongo.db.Teachers.find_one(
            {"_id": ObjectId(teacher_id)},
            {"_id": 0, "password": 0}  # Exclude sensitive data
        )
        
        if not teacher:
            return make_response(jsonify({"error": "Teacher not found"}), 404)

        return jsonify(teacher), 200

    except Exception as e:
        app.logger.error(f"Error getting teacher profile: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/users/<rfidUID>/add_loot_stacked_v2", methods=["POST"])
@require_api_key_strict
def add_loot_stacked_v2(rfidUID):
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        loot_name = data.get("lootName")
        count_to_add = data.get("count", 1)

        if not loot_name:
            return make_response(jsonify({"error": "Missing lootName"}), 400)

        # Check if loot already exists in user's collection
        user = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if not user:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        # Find existing loot
        existing_loot = None
        for i, loot in enumerate(user.get("loot", [])):
            if loot.get("name") == loot_name:
                existing_loot = {"loot": loot, "index": i}
                break

        if existing_loot:
            # Increment existing loot count
            result = mongo.db.Users.update_one(
                {"rfidUID": rfidUID, "loot.name": loot_name},
                {"$inc": {"loot.$.count": count_to_add}}
            )
        else:
            # Add new loot with count
            new_loot = {
                "name": loot_name,
                "count": count_to_add,
                "type": "loot"
            }
            result = mongo.db.Users.update_one(
                {"rfidUID": rfidUID},
                {"$push": {"loot": new_loot}}
            )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "Failed to update loot"}), 500)

        return jsonify({"message": f"Added {count_to_add} {loot_name}(s) successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding stacked loot: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

# Update the complete loot upload endpoint to handle stacking
@app.route("/api/v1/complete_loot_upload_stacked_v2", methods=["POST"])
@require_api_key_strict
def complete_loot_upload_stacked_v2():
    try:
        data = request.json
        app.logger.info(f"[complete_loot_upload_stacked_v2] Received data: {data}")
        
        rfid_uid = data.get('rfidUID')
        add_coins = data.get('addCoins', 0)
        creatures = data.get('creatures', [])
        loot = data.get('loot', [])
        challenge_code = data.get('challengeCode', '')  # ✅ ADD THIS LINE
        
        app.logger.info(f"[complete_loot_upload_stacked_v2] Processing - RFID: {rfid_uid}, Coins: {add_coins}")
        app.logger.info(f"[complete_loot_upload_stacked_v2] Challenge Code: {challenge_code}")  # ✅ ADD THIS LINE
        app.logger.info(f"[complete_loot_upload_stacked_v2] Creatures: {creatures}")
        app.logger.info(f"[complete_loot_upload_stacked_v2] Loot: {loot}")
        
        user = mongo.db.Users.find_one({"rfidUID": rfid_uid})
        if not user:
            app.logger.error(f"[complete_loot_upload_stacked_v2] User not found for RFID: {rfid_uid}")
            return make_response(jsonify({"error": "User not found"}), 404)
        
        app.logger.info(f"[complete_loot_upload_stacked_v2] Found user: {user['name']}")
        
        creatures_processed = 0
        loot_processed = 0
        
        # Process creatures with stacking
        for creature_data in creatures:
            creature_name = creature_data.get("name")
            creature_value = creature_data.get("value", 1)
            count = creature_data.get("count", 1)
            
            app.logger.info(f"[complete_loot_upload_stacked_v2] Processing creature: {creature_name}, value: {creature_value}, count: {count}")
            
            if not creature_name:
                app.logger.warning(f"[complete_loot_upload_stacked_v2] Skipping creature with no name: {creature_data}")
                continue
                
            # Check if creature already exists
            existing_creature = mongo.db.Users.find_one(
                {"rfidUID": rfid_uid, "creatures.name": creature_name}
            )
            
            if existing_creature:
                app.logger.info(f"[complete_loot_upload_stacked_v2] Incrementing existing creature {creature_name} by {count}")
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid, "creatures.name": creature_name},
                    {"$inc": {"creatures.$.count": count}}
                )
                app.logger.info(f"[complete_loot_upload_stacked_v2] Creature increment result: {result.modified_count}")
            else:
                app.logger.info(f"[complete_loot_upload_stacked_v2] Adding new creature {creature_name} with count {count}")
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid},
                    {"$push": {"creatures": {
                        "name": creature_name,
                        "value": creature_value,
                        "count": count
                    }}}
                )
                app.logger.info(f"[complete_loot_upload_stacked_v2] New creature result: {result.modified_count}")
            
            creatures_processed += 1
        
        # Process loot with stacking (existing code)
        for loot_data in loot:
            loot_name = loot_data.get("name")
            count = loot_data.get("count", 1)
            
            app.logger.info(f"[complete_loot_upload_stacked_v2] Processing loot: {loot_name}, count: {count}")
            
            if not loot_name:
                app.logger.warning(f"[complete_loot_upload_stacked_v2] Skipping loot with no name: {loot_data}")
                continue
            
            # Check if loot already exists
            existing_loot = mongo.db.Users.find_one(
                {"rfidUID": rfid_uid, "loot.name": loot_name}
            )
            
            if existing_loot:
                app.logger.info(f"[complete_loot_upload_stacked_v2] Incrementing existing loot {loot_name} by {count}")
                # Increment count
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid, "loot.name": loot_name},
                    {"$inc": {"loot.$.count": count}}
                )
                app.logger.info(f"[complete_loot_upload_stacked_v2] Loot increment result: {result.modified_count}")
            else:
                app.logger.info(f"[complete_loot_upload_stacked_v2] Adding new loot {loot_name} with count {count}")
                # Add new loot
                result = mongo.db.Users.update_one(
                    {"rfidUID": rfid_uid},
                    {"$push": {"loot": {
                        "name": loot_name,
                        "count": count,
                        "type": "loot"
                    }}}
                )
                app.logger.info(f"[complete_loot_upload_stacked_v2] New loot result: {result.modified_count}")
            
            loot_processed += 1
        
        # Add coins
        if add_coins > 0:
            app.logger.info(f"[complete_loot_upload_stacked_v2] Adding {add_coins} coins")
            coin_result = mongo.db.Users.update_one(
                {"rfidUID": rfid_uid},
                {"$inc": {"coins": add_coins}}
            )
            app.logger.info(f"[complete_loot_upload_stacked_v2] Coin update result: {coin_result.modified_count}")
        
        # ✅ ADD THIS SECTION - Store challenge code in array
        if challenge_code and challenge_code != '':
            app.logger.info(f"[complete_loot_upload_stacked_v2] Adding challenge code to array: {challenge_code}")
            
            # Add challenge code to challengeCodes array
            # Format: { "code": "1115", "digit": 5, "timestamp": datetime }
            # Extract the last digit (lives remaining)
            lives_remaining = int(challenge_code[-1]) if challenge_code[-1].isdigit() else 0
            base_code = challenge_code[:-1] if len(challenge_code) > 1 else challenge_code
            
            challenge_entry = {
                "code": challenge_code,      # Full code (e.g., "1115")
                "baseCode": base_code,       # Just the code part (e.g., "111")
                "livesRemaining": lives_remaining,  # Last digit (e.g., 5)
                "timestamp": datetime.datetime.utcnow()
            }
            
            challenge_result = mongo.db.Users.update_one(
                {"rfidUID": rfid_uid},
                {"$push": {"challengeCodes": challenge_entry}}
            )
            app.logger.info(f"[complete_loot_upload_stacked_v2] Challenge code added: {challenge_result.modified_count}")
        
        updated_user = mongo.db.Users.find_one({"rfidUID": rfid_uid})
        
        app.logger.info(f"[complete_loot_upload_stacked_v2] FINAL RESULT - User: {user['name']}, Creatures processed: {creatures_processed}, Loot processed: {loot_processed}, Total coins: {updated_user.get('coins', 0)}")
        
        return make_response(jsonify({
            "message": "Stacked upload successful",
            "coinsAdded": add_coins,
            "creaturesProcessed": creatures_processed,
            "lootProcessed": loot_processed,
            "challengeCodeAdded": challenge_code if challenge_code else None,  # ✅ ADD THIS LINE
            "totalCoins": updated_user.get("coins", 0)
        }), 200)
        
    except Exception as e:
        app.logger.error(f"[complete_loot_upload_stacked_v2] ERROR: {str(e)}")
        import traceback
        app.logger.error(f"[complete_loot_upload_stacked_v2] TRACEBACK: {traceback.format_exc()}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

def require_teacher_token(f):
    """Validate simple teacher token returned at login: 'teacher_<id>_<email>'"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # ✅ Allow OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return make_response('', 204)
            
        auth = request.headers.get('Authorization') or request.headers.get('X-Teacher-Token')
        if not auth:
            return make_response(jsonify({"error": "Authorization header required"}), 401)
        
        # Accept "Bearer <token>" or raw token
        token = auth.split(' ').pop()
        teacher_id = kwargs.get('teacher_id') or kwargs.get('teacherId') or None
        if not teacher_id:
            return make_response(jsonify({"error": "Teacher id required in path"}), 400)

        # Find teacher and validate token matches simple format
        try:
            teacher = mongo.db.Teachers.find_one({"_id": ObjectId(teacher_id)})
        except:
            return make_response(jsonify({"error": "Invalid teacher ID"}), 400)
            
        if not teacher:
            return make_response(jsonify({"error": "Teacher not found"}), 404)

        expected = f"teacher_{teacher_id}_{teacher.get('email')}"
        if token != expected:
            return make_response(jsonify({"error": "Invalid teacher token"}), 401)

        return f(*args, **kwargs)
    return decorated

@app.route("/api/v1/teachers/<teacher_id>/award_coins", methods=["POST"])
@require_teacher_token
def teacher_award_coins(teacher_id):
    """
    Teacher can award coins to a student by providing:
    { rfidUID: 'ABC123', coins: 5, note: 'optional' }
    """
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        rfid_uid = data.get('rfidUID')
        coins = int(data.get('coins', 0))

        if not rfid_uid:
            return make_response(jsonify({"error": "rfidUID required"}), 400)
        if coins <= 0:
            return make_response(jsonify({"error": "coins must be > 0"}), 400)

        result = mongo.db.Users.update_one({"rfidUID": rfid_uid}, {"$inc": {"coins": coins}})
        if result.matched_count == 0:
            return make_response(jsonify({"error": "No user found for given rfidUID"}), 404)

        updated = mongo.db.Users.find_one({"rfidUID": rfid_uid}, {"_id": 0, "coins": 1, "name": 1})
        return jsonify({
            "message": f"Awarded {coins} coins to {updated.get('name', rfid_uid)}",
            "totalCoins": updated.get('coins', 0)
        }), 200

    except Exception as e:
        app.logger.error(f"Error in teacher_award_coins: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

@app.route("/api/v1/purchase_item", methods=["POST"])
@require_api_key_strict
def purchase_item():
    """
    ESP32 shop endpoint - handles item purchases
    Expects: { "rfidUID": "...", "itemName": "...", "itemCost": ... }
    Returns: { "success": true, "newCoinBalance": ..., "itemPurchased": "..." }
    """
    try:
        data = request.get_json()
        
        rfid_uid = data.get('rfidUID')
        item_name = data.get('itemName')
        item_cost = data.get('itemCost')
        
        # Validate input
        if not rfid_uid:
            return make_response(jsonify({"error": "rfidUID required"}), 400)
        if not item_name:
            return make_response(jsonify({"error": "itemName required"}), 400)
        if not item_cost or item_cost <= 0:
            return make_response(jsonify({"error": "itemCost must be > 0"}), 400)
        
        # Find user
        user = mongo.db.Users.find_one({"rfidUID": rfid_uid})
        if not user:
            return make_response(jsonify({"error": "User not found"}), 404)
        
        # Check if user has enough coins
        current_coins = user.get('coins', 0)
        if current_coins < item_cost:
            return make_response(jsonify({
                "error": "Not enough coins",
                "currentCoins": current_coins,
                "itemCost": item_cost
            }), 400)
        
        # Calculate new balance
        new_balance = current_coins - item_cost
        
        # Update user - deduct coins and add item to purchasedItems array
        result = mongo.db.Users.update_one(
            {"rfidUID": rfid_uid},
            {
                "$set": {"coins": new_balance},
                "$push": {
                    "purchasedItems": {
                        "itemName": item_name,
                        "cost": item_cost,
                        "purchaseDate": datetime.datetime.utcnow()
                    }
                }
            }
        )
        
        if result.modified_count == 0:
            return make_response(jsonify({"error": "Failed to update user"}), 500)
        
        app.logger.info(f"User {rfid_uid} purchased {item_name} for {item_cost} coins. New balance: {new_balance}")
        
        return jsonify({
            "success": True,
            "message": f"Successfully purchased {item_name}",
            "itemPurchased": item_name,
            "itemCost": item_cost,
            "newCoinBalance": new_balance
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error in purchase_item: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)





