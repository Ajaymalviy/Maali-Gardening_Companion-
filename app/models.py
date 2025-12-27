from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from flask_login import UserMixin
from bson.objectid import ObjectId
from datetime import datetime
import google.generativeai as genai
import os

# Set up logging
logging.basicConfig(level=logging.ERROR)

# Configure the Gemini API
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)

# MongoDB Helper
def get_db():
    """Helper function to get MongoDB connection."""
    return current_app.config['DB_CONNECTION']

class User(UserMixin):
    def __init__(self, full_name, id, username, email, phone_no=None, role='user'):
        self.id = id
        self.full_name = full_name
        self.username = username
        self.email = email
        self.phone_no = phone_no
        self.role = role
    def get_id(self):
        return str(self.id)
    @staticmethod
    def find_by_identifier(identifier):
        """Find a user by username, email, or phone number."""
        db = get_db()
        return db.users.find_one({
            "$or": [
                {"username": identifier},
                {"email": identifier},
                {"phone_no": identifier}
            ]
        })

    @staticmethod
    def find_by_email(email):
        """Find a user by email."""
        db = get_db()
        return db.users.find_one({"email": email})

    @staticmethod
    def find_by_username(username):
        """Find a user by username."""
        db = get_db()
        return db.users.find_one({"username": username})

    @staticmethod
    def find_by_phone_no(phone_no):
        """Find a user by phone number."""
        db = get_db()
        return db.users.find_one({"phone_no": phone_no})

    @staticmethod
    def create_user(full_name, username, email, password, phone_no, role='user', status='active', profile_pic=None):
        """Create a new user in the database."""
        db = get_db()
        user_data = {
            "full_name": full_name,
            "username": username,
            "email": email,
            "phone_no": phone_no,
            "role": role,
            "status": status,
            "profile_pic": profile_pic 
        }
            # Only add hashed password if one is provided (i.e., non-OAuth users)
        if password:
            user_data["password_hash"] = generate_password_hash(password)

        result = db.users.insert_one(user_data)
        return str(result.inserted_id)

    @staticmethod
    def check_password(user, password):
        """Check if the provided password matches the user's hashed password."""
        return check_password_hash(user['password_hash'], password)

    @staticmethod
    def get_all_users():
        """Get all users for admin dashboard."""
        db = get_db()
        return list(db.users.find({}, {"_id": 1, "full_name": 1, "username": 1, "email": 1, "phone_no": 1, "status": 1, "role": 1}))

    @staticmethod
    def delete_user(user_id):
        """Delete a user."""
        db = get_db()
        return db.users.delete_one({"_id": ObjectId(user_id)})

    @staticmethod
    def update_user_role(user_id, new_role):
        """Update a user's role."""
        db = get_db()
        return db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": new_role}})

    @staticmethod
    def username_exists(username, exclude_email=None):
        """Check if username exists, optionally excluding a specific email."""
        db = get_db()
        query = {"username": username}
        if exclude_email:
            query["email"] = {"$ne": exclude_email}
        return bool(db.users.find_one(query))

    @staticmethod
    def phone_no_exists(phone_no, exclude_email=None):
        """Check if phone number exists, optionally excluding a specific email."""
        db = get_db()
        query = {"phone_no": phone_no}
        if exclude_email:
            query["email"] = {"$ne": exclude_email}
        return bool(db.users.find_one(query))

    @staticmethod
    def update_user(user_id, updates):
        """Update user information."""
        db = get_db()
        return db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})

    @staticmethod
    def update_password(email, new_password):
        """Update user password."""
        db = get_db()
        hashed_password = generate_password_hash(new_password)
        return db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hashed_password}}
        )

class Plant:
    @staticmethod
    def get_all_plants():
        """Get all plants."""
        db = get_db()
        return list(db.plants.find({}, {"_id": 1, "commonName": 1, "scientificName": 1, "familyCommonName": 1, "edible": 1, "genus": 1, "imageURL": 1}))

    @staticmethod
    def get_plant_by_id(plant_id):
        """Get plant by ID."""
        db = get_db()
        return db.plants.find_one({"_id": ObjectId(plant_id)})

    @staticmethod
    def add_plant(plant_data):
        """Add a new plant."""
        db = get_db()
        result = db.plants.insert_one(plant_data)
        return str(result.inserted_id)

    @staticmethod
    def update_plant(plant_id, update_data):
        """Update plant information."""
        db = get_db()
        return db.plants.update_one({"_id": ObjectId(plant_id)}, {"$set": update_data})

    @staticmethod
    def delete_plant(plant_id):
        """Delete a plant."""
        db = get_db()
        return db.plants.delete_one({"_id": ObjectId(plant_id)})

class Garden:
    @staticmethod
    def ensure_default_garden(user_id):
        """Ensure every user has a default garden."""
        db = get_db()
        default_garden = db.garden.find_one({"user_id": ObjectId(user_id)})
        
        if not default_garden:
            default_garden_id = db.garden.insert_one({
                "gardenName": "My Garden",
                "user_id": ObjectId(user_id),
                "created_at": datetime.now()
            }).inserted_id
        else:
            default_garden_id = default_garden["_id"]
        
        return str(default_garden_id)

    @staticmethod
    def get_user_gardens(user_id):
        """Get all gardens for a user."""
        db = get_db()
        return list(db.garden.find({"user_id": ObjectId(user_id)}, {"gardenName": 1}))

    @staticmethod
    def add_garden(user_id, garden_name):
        """Add a new garden for a user."""
        db = get_db()
        existing_garden = db.garden.find_one({
            "user_id": ObjectId(user_id),
            "gardenName": garden_name
        })
        
        if existing_garden:
            return None
        
        result = db.garden.insert_one({
            "gardenName": garden_name,
            "user_id": ObjectId(user_id),
            "created_at": datetime.now()
        })
        return str(result.inserted_id)

    @staticmethod
    def delete_garden(user_id, garden_id):
        """Delete a garden and its plants."""
        db = get_db()
        # Verify garden belongs to user
        garden = db.garden.find_one({"_id": ObjectId(garden_id), "user_id": ObjectId(user_id)})
        if not garden:
            return False
        
        db.garden.delete_one({"_id": ObjectId(garden_id)})
        db.garden_plant.delete_many({"garden_id": ObjectId(garden_id)})
        return True

class GardenPlant:
    @staticmethod
    def get_user_plants(user_id, garden_id):
        """Get all plants for a user in a specific garden."""
        db = get_db()
        # First get plant references from garden_plant
        user_plants_data = list(db.garden_plant.find(
            {"user_id": user_id, "garden_id": ObjectId(garden_id)},
            {"plant_id": 1, "_id": 0, "age_id": 1, "quantity": 1}
        ))
        
        if not user_plants_data:
            return []
            
        plant_ids = [entry["plant_id"] for entry in user_plants_data]
        
        # Get plant details
        plants = list(db.plants.find({"_id": {"$in": plant_ids}}))
        
        # Get age details
        age_ids = [entry["age_id"] for entry in user_plants_data]
        age_data = {str(age["_id"]): age["age"] for age in db.age.find({"_id": {"$in": age_ids}})}
        
        # Merge data
        final_plants = []
        for plant in plants:
            for entry in user_plants_data:
                if entry["plant_id"] == plant["_id"]:
                    plant_copy = plant.copy()
                    plant_copy["quantity"] = entry["quantity"]
                    plant_copy["age"] = age_data.get(str(entry["age_id"]), "Unknown")
                    final_plants.append(plant_copy)
                    
        return final_plants

    @staticmethod
    def add_plant_to_garden(user_id, garden_id, plant_id, age_id, plant_data):
        """Add a plant to a user's garden."""
        db = get_db()
        existing_plant = db.garden_plant.find_one({
            "user_id": user_id,
            "plant_id": ObjectId(plant_id),
            "garden_id": ObjectId(garden_id),
            "age_id": ObjectId(age_id)
        })
        
        if existing_plant:
            # Increment quantity if plant already exists
            db.garden_plant.update_one(
                {"_id": existing_plant["_id"]},
                {"$inc": {"quantity": 1}}
            )
            return "incremented"
        else:
            # Add new plant entry
            db.garden_plant.insert_one({
                "user_id": user_id,
                "plant_id": ObjectId(plant_id),
                "garden_id": ObjectId(garden_id),
                "age_id": ObjectId(age_id),
                "quantity": 1,
                **plant_data
            })
            return "added"

    @staticmethod
    def remove_plant_from_garden(user_id, garden_id, plant_id, age_id):
        """Remove or decrement a plant from a garden."""
        db = get_db()
        plant_entry = db.garden_plant.find_one({
            "user_id": user_id,
            "plant_id": ObjectId(plant_id),
            "garden_id": ObjectId(garden_id),
            "age_id": ObjectId(age_id)
        })
        
        if not plant_entry:
            return False
            
        if plant_entry["quantity"] > 1:
            # Decrement quantity
            db.garden_plant.update_one(
                {"_id": plant_entry["_id"]},
                {"$inc": {"quantity": -1}}
            )
            return "decremented"
        else:
            # Remove completely
            db.garden_plant.delete_one({"_id": plant_entry["_id"]})
            return "removed"

class Age:
    @staticmethod
    def get_all_ages():
        """Get all plant age categories."""
        db = get_db()
        return list(db.age.find())

class PlantRequest:
    @staticmethod
    def create_request(user_id, plant_name, description):
        """Create a new plant request."""
        db = get_db()
        result = db.plant_requests.insert_one({
            "plantName": plant_name,
            "description": description,
            "user_id": ObjectId(user_id),
            "status": "pending",
            "requested_at": datetime.now()
        })
        return str(result.inserted_id)

    @staticmethod
    def get_pending_requests():
        """Get all pending plant requests."""
        db = get_db()
        return list(db.plant_requests.find({"status": "pending"}))

    @staticmethod
    def delete_request(request_id):
        """Delete a plant request."""
        db = get_db()
        return db.plant_requests.delete_one({"_id": ObjectId(request_id)})

class ChatSession:
    def __init__(self, user_id):
        self.user_id = ObjectId(user_id)
        self.chat_data = self.load_chat_data()
        self.chat_history = self.load_chat_history()
        self.is_open = self.chat_data.get("is_open", False)

    def load_chat_data(self):
        db = get_db()
        chat_data = db.chat_data.find_one({"user_id": self.user_id})
        return chat_data if chat_data else {"is_open": False}

    def save_chat_data(self):
        db = get_db()
        db.chat_data.update_one(
            {"user_id": self.user_id},
            {"$set": {"is_open": self.is_open}},
            upsert=True
        )

    def load_chat_history(self):
        db = get_db()
        chat_history = db.chat_history.find_one({"user_id": self.user_id})
        return chat_history["history"] if chat_history else []

    def save_chat_history(self):
        db = get_db()
        db.chat_history.update_one(
            {"user_id": self.user_id},
            {"$set": {"history": self.chat_history}},
            upsert=True
        )

    def add_message(self, role, content):
        self.chat_history.append({"role": role, "content": content})
        self.save_chat_history()

    def clear_chat_history(self):
        self.chat_history = []
        self.save_chat_history()
        
    def toggle_chat(self):
        self.is_open = not self.is_open
        self.save_chat_data()

class GeminiHelper:
    @staticmethod
    def parse_gemini_response(response_text):
        """Parse the response from Gemini API to extract plant care details."""
        data = {}
        try:
            for line in response_text.split("\n"):
                if "Watering:" in line:
                    data['watering'] = int(line.split(":")[1].strip())
                elif "Fertilizing:" in line:
                    data['fertilizing'] = int(line.split(":")[1].strip())
                elif "Sunlight:" in line:
                    data['sunlight'] = int(line.split(":")[1].strip())
                elif "Fertilizer type:" in line:
                    data['fertilizer_type'] = line.split(":")[1].strip()
                elif "Soil type:" in line:
                    data['soil_type'] = line.split(":")[1].strip()
                elif "Change soil:" in line:
                    data['change_soil'] = int(line.split(":")[1].strip())
        except Exception as e:
            print(f"Error parsing response: {e}")
        return data

    @staticmethod
    def get_plant_care_info(plant_name):
        """Get plant care information from Gemini API."""
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (f"Give me watering and fertilizing schedule for {plant_name}, "
                "I just want numbers like in how many days return only a number, "
                "also give me the amount of sunlight it needs. In sunlight, give: "
                "1 for full sunlight, 2 for partial sunlight, 3 for no sunlight. "
                "Also give me the type of fertilizer recommended. in watering and fertilizing also only give a number in output not a interval"
                "Also give me type for soil recommended for my plant. in change_soil give number of months in which soil needs to be replaced.")

        response = model.generate_content(prompt)
        return response.text