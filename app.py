
#latest version trying to add coin to user value

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
        # Expecting a JSON body with "customName"
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        custom_name = data.get("customName")
        if not custom_name:
            return make_response(jsonify({"error": "customName is required"}), 400)

        # Attempt to update the user's coins by +5
        result = mongo.db.Users.update_one(
            {"customName": custom_name},
            {"$inc": {"coins": 5}}
        )

        if result.modified_count == 0:
            return make_response(jsonify({"error": "No user found for given customName"}), 404)

        return jsonify({"message": "5 coins added successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error adding 5 coins: {str(e)}")
        return make_response(jsonify({"error": "Internal Server Error"}), 500)


   
   
@app.route("/api/v1/create_user_from_rfid", methods=["POST"])
def create_user_from_rfid():
    try:
        data = request.json  # Expected fields: age, coins, creatureType, customName, intVal
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)
        
        # Extract data from the request
        age = data.get("age")
        coins = data.get("coins")
        creature_type = data.get("creatureType")
        custom_name = data.get("customName")
        int_val = data.get("intVal")
        
        # Validate required fields
        if age is None or coins is None or creature_type is None or custom_name is None or int_val is None:
            return make_response(jsonify({"error": "Missing required fields"}), 400)
        
        # Create the user document
        user = {
            "age": age,
            "coins": coins,
            "creatureType": creature_type,
            "customName": custom_name,
            "intVal": int_val
        }
        
        # Insert the user into the database
        result = mongo.db.Users.insert_one(user)
        
        return jsonify({"message": "User created successfully", "userId": str(result.inserted_id)}), 201
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



# Login route
@app.route('/api/v1/login', methods=['POST'])
def login():
    # Get username and password from request
    username = request.json.get('username')
    password = request.json.get('password')

    # Check if username and password are provided
    if not username or not password:
        return make_response(jsonify({"error": "Username and password are required"}), 400)

    # Check if the username and password match with database records
    user_data = mongo.db.Users.find_one({"username": username, "password": password})

    if user_data:
        print(user_data)
        # User authenticated successfully, return user-specific data
        return jsonify(user_data)
    else:
        return make_response(jsonify({"error": "Invalid username or password"}), 401)
    
    
    
# Account creation route
@app.route('/api/v1/create_account', methods=['POST'])
def create_account():
    # Get username and password from request
    username = request.json.get('username')
    password = request.json.get('password')
    classroom = request.json.get('classroom')

    # Check if username and password are provided
    if not username or not password:
        return make_response(jsonify({"error": "Username and password are required"}), 400)

    # Check if a user with the given username already exists
    existing_user = mongo.db.Users.find_one({"username": username})

    if existing_user:
        # User with the given username already exists, return an error
        return make_response(jsonify({"error": "Username already taken"}), 409)
    else:
        # Insert a new user into the database
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

        return jsonify({"message": "Account created successfully"})   
    
    


def add_item(username, item):
    try:
        # Add one item to the user's account in the database
        result = mongo.db.Users.update_one({"username": username}, {"$inc": {item: 1}})

        if result.modified_count == 0:
            return jsonify({"error": "No user found with given username"}), 404

        return jsonify({"message": f"1 {item} added successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



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



    