# New endpoint to add to app.py
# Place this after the teachers/register endpoint (around line 950)

@app.route("/api/v1/users/<rfidUID>/use_travel_item", methods=["POST"])
@require_api_key_optional
def use_travel_item(rfidUID):
    """
    Use a travel item to move to a new location
    - Sets currentLocation to the destination
    - Removes the used item from purchasedItems
    """
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        item_name = data.get("itemName")
        if not item_name:
            return make_response(jsonify({"error": "itemName is required"}), 400)

        # Map items to their destinations
        ITEM_TO_DESTINATION = {
            'boatTicketForest': 'HF',      # Greenwood Harbour
            'boatTicketLava': 'HL',        # Lavastone Harbour
            'boatTicketWater': 'HW',       # Water Harbour
            'wagonRide': 'FT',             # Town of Greenwood
            'machete': 'WT',               # Town of Bluehaven
            'lavaBoots': 'LT',             # Castle Emberfall
            'donkeyRide': 'MP',            # Mountain Pass
            'forestMap': 'CF',             # Forest Gate
            'gasMask': 'CL',               # Ashwood Pass
        }

        destination = ITEM_TO_DESTINATION.get(item_name)
        if not destination:
            return make_response(jsonify({"error": f"Unknown travel item: {item_name}"}), 400)

        # Find the user
        user = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if not user:
            return make_response(jsonify({"error": "User not found"}), 404)

        # Check if user has this item
        purchased_items = user.get("purchasedItems", [])
        has_item = any(item.get("itemName") == item_name for item in purchased_items)
        
        if not has_item:
            return make_response(jsonify({"error": f"User does not have {item_name}"}), 400)

        # Update: set currentLocation and remove the item
        mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {
                "$set": {"currentLocation": destination},
                "$pull": {"purchasedItems": {"itemName": item_name}}
            }
        )

        app.logger.info(f"✅ User {rfidUID} used {item_name} to travel to {destination}")

        return make_response(jsonify({
            "message": f"Traveled to {destination}",
            "currentLocation": destination,
            "itemUsed": item_name
        }), 200)

    except Exception as e:
        app.logger.error(f"Error using travel item: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 500)


@app.route("/api/v1/users/<rfidUID>/set_location", methods=["POST"])
@require_api_key_optional
def set_location(rfidUID):
    """
    Directly set a user's currentLocation (for admin/teacher use)
    """
    try:
        data = request.json
        if not data:
            return make_response(jsonify({"error": "No data provided"}), 400)

        location = data.get("location")
        if not location:
            return make_response(jsonify({"error": "location is required"}), 400)

        # Update the user's location
        result = mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {"$set": {"currentLocation": location}}
        )

        if result.matched_count == 0:
            return make_response(jsonify({"error": "User not found"}), 404)

        app.logger.info(f"✅ Set location for {rfidUID} to {location}")

        return make_response(jsonify({
            "message": f"Location set to {location}",
            "currentLocation": location
        }), 200)

    except Exception as e:
        app.logger.error(f"Error setting location: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 500)


@app.route("/api/v1/users/<rfidUID>/use_seize_power", methods=["POST"])
@require_api_key_strict
def use_seize_power(rfidUID):
    """
    Use SeizePower to take over the Lordship of the current location.
    Rules:
    - Player must have purchased a SeizePower item
    - Player must be at a location (currentLocation)
    - Automatically removes LordOf from previous lord (if any), sends them to 'H'
    - Sets activating player's lordOf to the location and removes the item
    """
    try:
        # Find activating user
        activator = mongo.db.Users.find_one({"rfidUID": rfidUID})
        if not activator:
            return make_response(jsonify({"error": "User not found"}), 404)

        current_location = activator.get("currentLocation")
        if not current_location:
            return make_response(jsonify({"error": "Activator has no currentLocation"}), 400)

        # Check purchased items for SeizePower (accept several variants)
        purchased_items = activator.get("purchasedItems", [])
        has_seize = any(
            (item.get("itemName") or "").lower() in ("seizepower", "seize_power", "seize-power")
            for item in purchased_items
        )

        if not has_seize:
            return make_response(jsonify({"error": "User does not have SeizePower"}), 400)

        # Find current lord (if any)
        current_lord = mongo.db.Users.find_one({"lordOf": current_location})

        # If current lord exists and is different from activator, demote them
        previous_lord_id = None
        if current_lord and current_lord.get("rfidUID") != rfidUID:
            previous_lord_id = current_lord.get("rfidUID")
            mongo.db.Users.update_one(
                {"rfidUID": current_lord.get("rfidUID")},
                {"$set": {"lordOf": None, "currentLocation": "H"}}
            )

        # Promote activator: set lordOf and remove the SeizePower item
        mongo.db.Users.update_one(
            {"rfidUID": rfidUID},
            {
                "$set": {"lordOf": current_location},
                "$pull": {"purchasedItems": {"itemName": {"$in": ["SeizePower", "seizePower", "seize_power", "seize-power"]}}}
            }
        )

        app.logger.info(f"✅ User {rfidUID} seized power at {current_location} (prev: {previous_lord_id})")

        return make_response(jsonify({
            "message": "SeizePower used",
            "location": current_location,
            "previousLord": previous_lord_id,
            "newLord": rfidUID
        }), 200)

    except Exception as e:
        app.logger.error(f"Error using SeizePower: {str(e)}")
        return make_response(jsonify({"error": str(e)}), 500)
