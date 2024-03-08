
import os
from flask import Flask, Response, request, jsonify, make_response
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.json_util import dumps
from bson.objectid import ObjectId
from flask_pymongo import PyMongo

load_dotenv()

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://colesluke:WZAQsanRtoyhuH6C@qrcluster.zxgcrnk.mongodb.net/playerData"
mongo = PyMongo(app)

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

@app.route('/api/v1/resources/<id>', methods=['DELETE'])
def delete_resource(id):
    mongo.db.Data.delete_one({'_id': ObjectId(id)})
    resp = jsonify({"message": "Resource deleted successfully"})
    resp.status_code = 200
    return resp 

@app.route('/api/v1/resources/<id>', methods=['PUT'])
def update_resource(id):
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

#if __name__ == "__main__":
#    app.run(debug=True)


if __name__ == "__main__":
    app.run(debug=True,)
    
    
'''   
    print(f"Debug: {app.debug}")
    print(f"Host: {app.run_host}")
    print(f"Port: {app.run_port}")
    app.run(host='0.0.0.0', port=5000, debug=False)
''' 