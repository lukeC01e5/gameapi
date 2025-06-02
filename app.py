#latest version trying to add coin to user value
#trying to change to the new version with two rfid blocks

import os
from flask import Flask, Response, render_template, request, jsonify, make_response
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask_pymongo import PyMongo
from flask.json import JSONEncoder  # Corrected import
from flask_cors import CORS
from flask import send_from_directory


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

load_dotenv()

app = Flask(__name__)
app.json_encoder = CustomJSONEncoder
CORS(app)


app.config["MONGO_URI"] = "mongodb+srv://colesluke:WZAQsanRtoyhuH6C@qrcluster.zxgcrnk.mongodb.net/playerData?retryWrites=true&w=majority&appName=qrCluster"

mongo = PyMongo(app)


@app.route("/")
def index():
    return render_template("index.html")

   # return send_from_directory('static/unity_build', 'index.html')
   

@app.route("/api/v1/add_5_coin", methods=["POST"])
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
def create_user_from_rfid():
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        # Adjust field names to match what you send from the ESP32
        name = data.get("name")            # old "playerName"
        password = data.get("password")    # old "playerPassword"
        rfidUID = data.get("rfidUID")
        playerClass = data.get("playerClass")  # NEW

        # We can make the other fields optional by using .get(..., defaultValue)
        mainCreature = data.get("mainCreature", "")
        challengeCodes = data.get("challengeCodes", [])
        creatures = data.get("creatures", [])
        artifacts = data.get("artifacts", [])

        # Check only the required ones for now
        if not all([
            name,
            password,
            rfidUID,
            playerClass
        ]):
            return make_response(jsonify({"error": "Missing required fields"}), 400)

        # Construct the user document
        # You can store "playerClass" under any name you like, e.g. "class" or "playerClass"
        user = {
            "name": name,
            "password": password,
            "rfidUID": rfidUID,
            "playerClass": playerClass,
            "mainCreature": mainCreature,
            "challengeCodes": challengeCodes,
            "creatures": creatures,
            "artifacts": artifacts
        }

        # Insert into "Users" collection
        result = mongo.db.Users.insert_one(user)

        return jsonify({
            "message": "User created successfully",
            "userId": str(result.inserted_id)
        }), 201

    except Exception as e:
        app.logger.error(f"Error creating user from RFID data: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


@app.route("/api/v1/get_custom_names", methods=["GET"])
def get_custom_names():
    try:
        # Retrieve only the 'customName' field from all documents
        users = mongo.db.Users.find({}, {"_id": 0, "customName": 1})
        
        # Build a list of custom names
        custom_names = [user["customName"] for user in users if "customName" in user]
        
        return jsonify(custom_names), 200
    except Exception as e:
        app.logger.error(f"Error fetching custom names: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)




@app.route('/api/v1/users', methods=['GET'])
def get_users():
    try:
        users = mongo.db.Users.find()
        users_list = list(users)  # Convert cursor to list
        return jsonify(users_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/v1/resources', methods=['GET'])
def get_resources():
    resources = mongo.db.Data.find()
    resp = dumps(resources)
    return resp

@app.route('/api/v1/resources', methods=['POST'])
def add_resource():
    _json = request.json
    mongo.db.Data.insert_one(_json)
    resp = jsonify({"message": "Resource added  successfully"})
    resp.status_code = 200
    return resp

@app.route('/api/v1/resources', methods=['DELETE'])
def delete_resource():
    mongo.db.Data.delete_one({'_id': ObjectId(id)})
    resp = jsonify({"message": "Resource deleted  successfully"})
    resp.status_code = 200
    return resp 

@app.route('/api/v1/resources', methods=['PUT'])
def update_resource():
    _json = request.json
    mongo.db.Data.update_one({'_id': ObjectId(id)}, {"$set": _json})
    resp = jsonify({"message": "Resource updated  successfully"})
    resp.status_code = 200
    return resp

@app.route("/api/v1/users/<rfidUID>/add_creature", methods=["POST"])
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


@app.route("/api/v1/users", methods=["GET"])
def get_user_by_rfid():
    try:
        # Get the rfidUID from the query parameters
        rfid_uid = request.args.get("rfidUID")
        if not rfid_uid:
            return make_response(jsonify({"error": "rfidUID is required"}), 400)

        # Query the database for the user with the given rfidUID
        user = mongo.db.Users.find_one({"rfidUID": rfid_uid}, {"_id": 0, "name": 1})

        if not user:
            return make_response(jsonify({"error": "No user found for the given rfidUID"}), 404)

        # Return the user's name
        return jsonify({"playerName": user["name"]}), 200

    except Exception as e:
        app.logger.error(f"Error fetching user by RFID: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)

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
    # Log the error
    app.logger.error(str(e))

    # Return a generic server error message
    return make_response(jsonify({"errorCode": 500, 
                                  "errorDescription": "Internal Server Error",
                                  "errorDetailedDescription": str(e),
                                  "errorName": "Internal Server Error"}), 500)


if __name__ == "__main__":
    app.run(debug=True,)



