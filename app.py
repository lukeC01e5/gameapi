
import os
from flask import Flask, Response, request, jsonify, make_response
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask_pymongo import PyMongo
from bson import ObjectId
from flask import Flask, json
from flask.json import JSONEncoder
from flask import Flask, render_template, send_from_directory


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


load_dotenv()

app = Flask(__name__)
app.json_encoder = CustomJSONEncoder
app.config["MONGO_URI"] = "mongodb+srv://colesluke:WZAQsanRtoyhuH6C@qrcluster.zxgcrnk.mongodb.net/playerData?retryWrites=true&w=majority&appName=qrCluster"

mongo = PyMongo(app)


@app.route('/', methods=['GET'])
def home():
    return "Welcome to my API!"




# Route to serve Unity WebGL build
@app.route('/unity')
def unity():
    return render_template('unity_build/index.html')

# Optional: Serve static files directly (e.g., .js, .data files)
@app.route('/unity/<path:filename>')
def unity_static(filename):
    return send_from_directory('static/unity_build', filename)





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
# Account creation route
@app.route('/api/v1/create_account', methods=['POST'])
def create_account():
    # Get username and password from request
    username = request.json.get('username')
    password = request.json.get('password')

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
            "coin": 0, 
            "meat": 0, 
            "plant": 0, 
            "crystal": 0, 
            "water": 0
        })

        return jsonify({"message": "Account created successfully"})   
    
    
    
    
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
        # Add one item to the user's account in the database
        result = mongo.db.Users.update_one({"username": username}, {"$inc": {item: 1}})

        if result.modified_count == 0:
            return jsonify({"error": "No user found with given username"}), 404

        return jsonify({"message": f"1 {item} added successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



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
        # Add one creature to the user's account in the database
        result = mongo.db.Users.update_one({"username": username}, {"$push": {"creatures": creature}})

        if result.modified_count == 0:
            return jsonify({"error": "No user found with given username"}), 404

        return jsonify({"message": f"1 {creature} added successfully"}), 200

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
    resp = jsonify({"message": "Resource added successfully"})
    resp.status_code = 200
    return resp

@app.route('/api/v1/resources', methods=['DELETE'])
def delete_resource():
    mongo.db.Data.delete_one({'_id': ObjectId(id)})
    resp = jsonify({"message": "Resource deleted successfully"})
    resp.status_code = 200
    return resp 

@app.route('/api/v1/resources', methods=['PUT'])
def update_resource():
    _json = request.json
    mongo.db.Data.update_one({'_id': ObjectId(id)}, {"$set": _json})
    resp = jsonify({"message": "Resource updated successfully"})
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



    
