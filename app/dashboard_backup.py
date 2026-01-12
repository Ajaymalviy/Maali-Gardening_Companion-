from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
import google.generativeai as genai
from functools import wraps
import os
from bson.objectid import ObjectId
from .models import User
from datetime import datetime
from flask import render_template, request, jsonify


# Initialize blueprint
dashboard_bp = Blueprint('dashboard', __name__)

# Configure the Gemini API

api_key = 'AIzaSyAgiXHaX1IuWDErnEwfXdYRWMGhKUCehs0'  # Use environment variable for API key
genai.configure(api_key=api_key)


# Utility: Role-based access decorator
def role_required(*roles):
    """
    Restricts access based on user roles.
    Args:
        role (str): Required role ('admin', 'client', etc.).
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("You need to log in to access this page.", "error")
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:  # Allow multiple roles
                flash("You do not have permission to access this page.", "error")
                return redirect(url_for("auth.login"))
            return func(*args, **kwargs)
        return wrapper
    return decorator


@dashboard_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required('user', 'admin')
def dashboard():
    try:
        # Access the MongoDB database
        db = current_app.config['DB_CONNECTION']
        default_garden_id = ensure_default_garden(current_user.id)
        garden_id = request.form.get('garden_id') or request.args.get('garden_id')
        garden_id = garden_id or default_garden_id  # Handle invalid format
        # print("default",default_garden_id)
        # print("Extracted garden_id:", garden_id)
        #list of user garden
        id_current_user = ObjectId(current_user.id)
        user_id = ObjectId(current_user.id)
        print('current user id is ', user_id)
        chat_session = ChatSession(user_id)
        user_garden = list(db.garden.find({"user_id": id_current_user},{"gardenName":1}))

        if not garden_id and user_garden:
            print("first",str(user_garden[0]['_id']))
            garden_id = str(user_garden[0]['_id'])  # Set first garden as default
        try:
            garden_obj_id=ObjectId(garden_id)
        except Exception as e:
            garden_obj_id=ObjectId(default_garden_id)
        user_plants = list(db.garden_plant.find({"user_id": current_user.id, "garden_id": garden_obj_id}))
        user_plants_data = list(db.garden_plant.find({"user_id": current_user.id,"garden_id": garden_obj_id}, {"plant_id": 1, "_id": 0, "age_id": 1, "quantity": 1,}))
        # print(user_plants)
        plant_ids = [entry["plant_id"] for entry in user_plants_data]
        
        # Fetch full plant details from plants collection
        user_plants = list(db.plants.find({"_id": {"$in": plant_ids}}))
        plants = list(db.plants.find())
        
         
        user = db.users.find_one({"_id": ObjectId(current_user.id)}, {"role": 1, "_id": 0})
        print('current user is ', user)
        user_role = user["role"]
        age=list(db.age.find())
        gemini_response = None
        # Step 1: Fetch quantity details from garden_plant
        plant_details = {}
        garden_plants = db.garden_plant.find(
            {"user_id": current_user.id, "garden_id": garden_obj_id},
            {"plant_id": 1, "garden_id": 1, "age_id": 1, "quantity": 1, "_id": 0}
        )

        for gp in garden_plants:
            plant_id = str(gp["plant_id"])  # Convert to string
            age_id = str(gp["age_id"])  # Convert age_id to string for key

            key = (plant_id, age_id)  # Tuple as key to differentiate by age

            if key in plant_details:
                plant_details[key]["quantity"] += gp["quantity"]  # Increase quantity
            else:
                plant_details[key] = {
                    "garden_id": gp["garden_id"],
                    "age_id": age_id,
                    "quantity": gp["quantity"]
                }
        user_plants = list(db.plants.find({"_id": {"$in": plant_ids}}))

        # Step 3: Merge quantity data into user_plants
                # Fetch plant details from plants collection
        plant_ids = list(set([ObjectId(k[0]) for k in plant_details.keys()]))  # Unique plant_ids
        user_plants = list(db.plants.find({"_id": {"$in": plant_ids}}))

        # Fetch age details from age collection
        age_ids = list(set([ObjectId(k[1]) for k in plant_details.keys()]))  # Unique age_ids
        age_data = {str(age["_id"]): {"age": age["age"], "age_id": str(age["_id"])} for age in db.age.find({"_id": {"$in": age_ids}})}
        # Merge data
        final_plants = []
        for plant in user_plants:
            plant_id_str = str(plant["_id"])
            for (pid, age_id), details in plant_details.items():
                if pid == plant_id_str:
                    plant_copy = plant.copy()
                    plant_copy["quantity"] = details["quantity"]
                    plant_copy["garden_id"] = details["garden_id"]
                    age_info = age_data.get(details["age_id"], {"age": "Unknown", "age_id": details["age_id"]})
                    plant_copy["age"] = age_info["age"]
                    plant_copy["age_id"] = age_info["age_id"]  # Fetch age
                    final_plants.append(plant_copy)
        # print(final_plants)


        # Handle POST Requests
        if request.method == 'POST':
            print('my post method is worked')
            # When the user selects a different garden
            if 'select_garden' in request.form:
                garden_id = request.form.get('garden_id') or default_garden_id
                print('garden id is', garden_id)
                # print("select")
                return redirect(url_for('dashboard.dashboard', garden_id=str(garden_obj_id)))

            if 'add_plant' in request.form:
                # print("garden id", garden_id)
                plant_id = request.form.get('plant_id')
                plant_id = ObjectId(plant_id)
                age_id = request.form.get('age_id')
                age_id = ObjectId(age_id)
                print('plant and age id is ', plant_id, age_id)


                if plant_id:
                    try:
                        # Fetch plant information from the database
                        plant_info = db.plants.find_one({"_id": plant_id})
                        if not plant_info:
                            flash("Plant not found in the database.", "warning")
                            return redirect(url_for('dashboard.dashboard', garden_id=garden_id))

                        plant_common_name = plant_info.get("commonName", "Unknown")

                        # Check if scheduling information exists
                        if all(key in plant_info for key in ["watering", "fertilizing", "sunlight", "fertilizer_type", "soil_type", "change_soil"]):
                            data = {
                                "watering": plant_info["watering"],
                                "fertilizing": plant_info["fertilizing"],
                                "sunlight": plant_info["sunlight"],
                                "fertilizer_type": plant_info["fertilizer_type"],
                                "soil_type": plant_info["soil_type"],
                                "change_soil": plant_info["change_soil"]
                            }
                        else:
                            # Fetch scheduling details from Gemini API
                            model = genai.GenerativeModel("gemini-1.5-flash")
                            prompt = (f"Give me watering and fertilizing schedule for {plant_common_name}, "
                                    "I just want numbers like in how many days return only a number, "
                                    "also give me the amount of sunlight it needs. In sunlight, give: "
                                    "1 for full sunlight, 2 for partial sunlight, 3 for no sunlight. "
                                    "Also give me the type of fertilizer recommended. in watering and fertilizing also only give a number in output not a interval"
                                    "Also give me type for soil recommended for my plant. in change_soil give number of months in which soil needs to be replaced.")

                            response = model.generate_content(prompt)
                            gemini_response = response.text
                            data = parse_gemini_response(gemini_response)

                            if data:
                                db.plants.update_one(
                                    {"_id": plant_id},
                                    {"$set": {
                                        "watering": data["watering"],
                                        "fertilizing": data["fertilizing"],
                                        "sunlight": data["sunlight"],
                                        "fertilizer_type": data["fertilizer_type"],
                                        "soil_type": data["soil_type"],
                                        "change_soil": data["change_soil"]
                                    }}
                                )

                        # Check if plant already exists with same age_id
                        existing_plant = db.garden_plant.find_one({
                            "user_id": current_user.id,
                            "plant_id": plant_id,
                            "garden_id": ObjectId(garden_obj_id),
                            "age_id": age_id
                        })

                        if existing_plant:
                            # If plant exists, increment quantity
                            db.garden_plant.update_one(
                                {"_id": existing_plant["_id"]},
                                {"$inc": {"quantity": 1}}
                            )
                            flash(f"Another {plant_common_name} has been added to your garden!", "success")
                        else:
                            # Otherwise, create a new entry with quantity 1
                            db.garden_plant.insert_one({
                                "user_id": current_user.id,
                                "plant_id": plant_id,
                                "garden_id": ObjectId(garden_obj_id),
                                "watering": data["watering"],
                                "fertilizing": data["fertilizing"],
                                "sunlight": data["sunlight"],
                                "fertilizer_type": data["fertilizer_type"],
                                "soil_type":data["soil_type"],
                                "change_soil":data["change_soil"],
                                "plant_common_name": plant_common_name,
                                "age_id": age_id,
                                "quantity": 1  # Start with quantity 1
                            })
                                                       # 🔔 Send Email Notification
                            user = db.users.find_one({"_id": ObjectId(current_user.id)})
                            print('user is ', user)
                            if user:
                                print('user is present and notification is sended')
                                subject = f"New Plant Added to Your Garden: {plant_common_name}"
                                body = f"""
                                    Hello {user['full_name']},

                                    A new plant has been added to your garden:

                                    🌱 Common Name: {plant_common_name}
                                    💧 Watering every {data['watering']} days
                                    🌞 Sunlight requirement: {data['sunlight']}
                                    🌾 Fertilizer: {data['fertilizer_type']}
                                    🪴 Soil Type: {data['soil_type']}
                                    ♻️ Change soil every {data['change_soil']} months

                                    Happy Gardening! 🌼

                                    - Garden Team
                                """
                                send_email_task.delay(
                                    subject=subject,
                                    recipients=[user['email']],
                                    body=body
                                )
                            flash(f"{plant_common_name} has been added to your garden!", "success")

                    except Exception as e:
                        flash(f"Error adding plant: {str(e)}", "danger")

                return redirect(url_for('dashboard.dashboard', garden_id=str(garden_obj_id)))
            if 'remove_plant' in request.form:
                    plant_id = ObjectId(request.form.get('plant_id'))
                    age_id = ObjectId(request.form.get('age_id'))  # Age ID ko bhi lena hoga
                    garden_id = ObjectId(request.form.get('garden_id'))
                    print("remove",garden_id)
                    # Fetch current plant details
                    plant_entry = db.garden_plant.find_one(
                        {"user_id": current_user.id, "plant_id": plant_id, "garden_id": garden_id, "age_id": age_id}
                    )

                    if plant_entry:
                        if plant_entry["quantity"] > 1:
                            # Reduce quantity by 1 if more than 1 exists
                            db.garden_plant.update_one(
                                {"user_id": current_user.id, "plant_id": plant_id, "garden_id": garden_id, "age_id": age_id},
                                {"$inc": {"quantity": -1}}
                            )
                            flash("Plant quantity decreased.", "success")
                        else:
                            # Remove entry if quantity is 1 (so it becomes 0)
                            db.garden_plant.delete_one(
                                {"user_id": current_user.id, "plant_id": plant_id, "garden_id": garden_id, "age_id": age_id}
                            )
                            flash("Plant removed completely.", "success")
                    else:
                        flash("Plant not found.", "danger")

                    return redirect(url_for('dashboard.dashboard', garden_id=garden_id))
        # Render Template with the selected garden's plant
        # print("garden obj id ",garden_obj_id)
        return render_template(
            'dashboard.html',
            user_plants=final_plants,
            user_plants_data=user_plants_data,
            plants=plants,
            user_role=user_role,
            user_garden=user_garden,
            selected_garden=str(garden_obj_id),
            gemini_response=gemini_response,
            chatbot_open=chat_session.is_open, # Updated to use chat_session
            chat_history=chat_session.chat_history,
            age=age,
            garden_id=str(garden_obj_id))
    except Exception as e:
        print(f"Error in dashboard: {e}")
        return render_template('error.html', error_message="Something went wrong. Please try again later."), 500

@dashboard_bp.route("/add_garden", methods=["POST"])
def add_garden():
    garden_name = request.form.get("garden_name")
    user_id = current_user.id  # Replace with your user session ID retrieval

    # Fetch the MongoDB connection from the current app context
    db = current_app.config['DB_CONNECTION']
    user_garden = list(db.garden.find({"user_id": ObjectId(user_id)}, {"gardenName": 1, "_id": 0}))

# Extract garden names from the list of dictionaries
    existing_garden_names = [garden["gardenName"] for garden in user_garden]

    # print(garden_name)
    # print(existing_garden_names)

    if garden_name in existing_garden_names:
        flash("Error: Garden name already exists. Cannot add the same garden name.", "danger")
        return redirect(url_for("dashboard.dashboard"))
    else:

        if garden_name and user_id:
            
            result=db.garden.insert_one({

                "gardenName": garden_name,
                "user_id": ObjectId(user_id),
                "created_at": datetime.now()
            })
            new_garden_id=str(result.inserted_id)  #convert to string 
            flash("Garden added successfully!")
            return redirect(url_for("dashboard.dashboard",garden_id=new_garden_id))
    return redirect(url_for("dashboard.dashboard"))

def ensure_default_garden(user_id):
    db = current_app.config['DB_CONNECTION']
    
    default_garden = db.garden.find_one({"user_id": ObjectId(user_id)})
    # print(default_garden)
    if not default_garden:
        default_garden_id = db.garden.insert_one({
            "gardenName": "My Garden",
            "user_id": ObjectId(user_id),
            "created_at": datetime.now()
        }).inserted_id
    else:
        default_garden_id = default_garden["_id"]
    
    # print(str(default_garden_id))
    return str(default_garden_id)  # Ensure it's a string for URL usage

def get_user_plants(db, user_id, garden_id):
    """Fetch the plants belonging to a specific user and garden from MongoDB"""
    try:
        print(f"Checking plants for User ID: {user_id} in Garden ID: {garden_id}")

        garden_obj_id = ObjectId(garden_id)  # Convert garden_id to ObjectId
        

        # Query the garden_plant collection for user's plants in the selected garden
        user_plants = list(db.garden_plant.find({"user_id": current_user.id, "garden_id": garden_obj_id}))

        print("Query Result:", user_plants)
        if not user_plants:
            return "You haven't added any plants to this garden yet."

        # Format response
        response_text = "Here are your plants in this garden:\n\n"
        for plant in user_plants:
            response_text += (f"🌿 {plant['plant_common_name']} \n")
                              
        
        return response_text

    except Exception as e:
        return f"Error retrieving plants: {str(e)}"

    

# # Helper Function: Parse Gemini Response
def parse_gemini_response(response_text):
    """
    Parse the response from Gemini API to extract plant care details.
    """
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

model = genai.GenerativeModel("gemini-1.5-flash")

# Add the missing methods to ChatSession class
class ChatSession:
    def __init__(self, user_id):
        self.user_id = ObjectId(user_id)  # Ensure user_id is an ObjectId
        self.chat_data = self.load_chat_data()
        self.chat_history = self.load_chat_history()
        self.is_open = self.chat_data.get("is_open", False) 

    def load_chat_data(self):
        db = current_app.config['DB_CONNECTION']
        chat_data = db.chat_data.find_one({"user_id": self.user_id})
        return chat_data if chat_data else {"is_open": False}

    def save_chat_data(self):
        db = current_app.config['DB_CONNECTION']
        db.chat_data.update_one(
            {"user_id": self.user_id},
            {"$set": {"is_open": self.is_open}},
            upsert=True
        )

    def load_chat_history(self):
        db = current_app.config['DB_CONNECTION']
        chat_history = db.chat_history.find_one({"user_id": self.user_id})
        return chat_history["history"] if chat_history else []

    def save_chat_history(self):
        db = current_app.config['DB_CONNECTION']
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
        self.is_open = not self.is_open  # Toggle chatbot open state
        self.save_chat_data()

# chat_session = ChatSession(current_user.id)

def create_structured_prompt(user_input, chat_history):
    # Create a more specific prompt structure
    base_prompt = """
    As a plant expert, provide to the point, brief and  specific answers in cute  kawaii tone and language about:
    - Plant care and maintenance
    - Plant diseases and treatments
    - Gardening techniques
    - Plant identification
    - Botanical information
    
    Format your response as:
    1. Direct answer to the question
    2. Additional relevant details
    but only when this format is applicable and relevant to their question
    
    only if they say hello or greet you, greet them back and 
    if answer is not plant specific reply: please ask plant specific questions!!
    don't start response with Plantie 🌼: 
    response should be in kawaii manner and you are tell somethhing to your friend.
    
    Previous context:
    {context}
    
    Current question: {question}
    """
    
    # Format the context from chat history
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-15:]])  # Last 15 messages
    return base_prompt.format(context=context, question=user_input)

def chatbot_response(prompt, chat_history, user_id=None, garden_id=None, db=None):
    try:
        # Detect if user is asking about their plants
        if "my plant" in prompt.lower() or "list my plants" in prompt.lower():
            return get_user_plants(db, user_id, garden_id)
        # Create structured prompt
        full_prompt = create_structured_prompt(prompt, chat_history)
        
        # Generate response with specific parameters
        response = model.generate_content(
            full_prompt,
            generation_config={
                'temperature': 0.7,  # Balance between creativity and consistency
                'top_p': 0.8,        # Nucleus sampling parameter
                'top_k': 40,         # Limit vocabulary diversity
                'max_output_tokens': 500  # Reasonable response length
            }
        )
        
        if response and hasattr(response, "text"):
            # Process the response to ensure it's specific
            processed_response = response.text.strip()
            
            # Verify if response is plant-related
            # if not any(keyword in processed_response.lower() for keyword in 
            #           ['plant', 'garden', 'soil', 'water', 'grow', 'leaf', 'root']):
            #     return "Please ask only plant-related questions!"
                
            return processed_response
            
        return "I apologize, but I couldn't generate a specific response. Please try rephrasing your question."
    
    except Exception as e:
        return f"An error occurred: {str(e)}. Please try again with a different question."

@dashboard_bp.route('/chatbot_toggle', methods=['POST'])
@login_required
def chatbot_toggle():
    user_id = current_user.get_id()
    chat_session = ChatSession(user_id)
    chat_session.toggle_chat()  # Toggle chatbot state and save it
    return redirect(url_for('dashboard.dashboard'))

@dashboard_bp.route('/chatbot', methods=['POST'])
@login_required
def chatbot():
    user_id = ObjectId(current_user.id)  # Convert to ObjectId
    chat_session = ChatSession(user_id)
    
    user_message = request.form.get("message", "").strip()
    
    if not user_message:
        return redirect(url_for('dashboard.dashboard'))

    db = current_app.config['DB_CONNECTION']

    garden_id = request.args.get("garden_id") or request.form.get("garden_id")
    
    if not garden_id:
        user_garden = db.garden.find_one({"user_id": user_id}, {"_id": 1})
        if not user_garden:
            flash("You don't have any gardens. Please create one first.", "warning")
            return redirect(url_for('dashboard.dashboard'))
        garden_id = str(user_garden["_id"])

    chat_session.add_message("User", user_message)
    
    response = chatbot_response(user_message, chat_session.chat_history, user_id, garden_id, db)
    chat_session.add_message("Plantie 🌼", response)
    
    return redirect(url_for('dashboard.dashboard', garden_id=garden_id))
# Route to render admin dashboard
@dashboard_bp.route("/admin", methods=["POST","GET"])
def admin_dashboard():
    db = current_app.config['DB_CONNECTION']
    users = list(db.users.find({}, {"_id": 1, "full_name": 1, "username": 1, "email": 1, "phone_no": 1, "status": 1, "role": 1}))
    plants = list(db.plants.find({}, {"_id": 1, "commonName": 1, "scientificName": 1, "familyCommonName": 1, "edible": 1,"genus":1,"imageURL":1}))
    return render_template("admin.html", users=users, plants=plants)



# # Delete a plant
@dashboard_bp.route("/delete_plant/<plant_id>", methods=["DELETE"])
def delete_plant(plant_id):
    db = current_app.config['DB_CONNECTION']
    print("Deleting plant:", plant_id)
    db.plants.delete_one({"_id": ObjectId(plant_id)})  #  Fix: Convert to ObjectId
    print("Deleting plant:", plant_id)

    users = list(db.users.find({}, {"_id": 1, "full_name": 1, "username": 1, "email": 1, "phone_no": 1, "status": 1, "role": 1}))
    plants = list(db.plants.find({}, {"_id": 1, "commonName": 1, "scientificName": 1, "familyCommonName": 1, "edible": 1,"genus":1,"imageURL":1})) # ✅ Fix: Convert to ObjectId
    return jsonify({"message": "plant deleted successfully!"})

# Delete a user
@dashboard_bp.route("/delete_user/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    print("Deleting user:", user_id)
    db = current_app.config['DB_CONNECTION']
    db.users.delete_one({"_id": ObjectId(user_id)}) 
    print("Deleting user:", user_id)

    users = list(db.users.find({}, {"_id": 1, "full_name": 1, "username": 1, "email": 1, "phone_no": 1, "status": 1, "role": 1}))
    plants = list(db.plants.find({}, {"_id": 1, "commonName": 1, "scientificName": 1, "familyCommonName": 1, "edible": 1,"genus":1,"imageURL":1})) # ✅ Fix: Convert to ObjectId
    return jsonify({"message": "User deleted successfully!"})

# Update a user's role
@dashboard_bp.route("/update_user_role/<user_id>", methods=["PUT"])
def update_user_role(user_id):
    print("update")
    data = request.json
    new_role = data.get("role", "")
    print(new_role)
    db = current_app.config['DB_CONNECTION']
    db.users.update_one({"_id"  : ObjectId(user_id)}, {"$set": {"role": new_role}})  # ✅ Fix: Convert to ObjectId
    return jsonify({"message": "User role updated successfully!"})

from tasks import send_email_task

@dashboard_bp.route('/add_plant', methods=['GET', 'POST'])
@login_required
def add_plant():
    print('i am in add plant')
    if current_user.role != 'admin':
        return redirect(url_for('dashboard.dashboard'))

    db = current_app.config['DB_CONNECTION']

    # If it's a GET request, show the form with pre-filled values
    if request.method == 'GET':
        # users = list(db.users.find({}, {"_id": 1, "full_name": 1, "username": 1, "email": 1, "phone_no": 1, "status": 1, "role": 1}))
        # plants = list(db.plants.find({}, {"_id": 1, "commonName": 1, "scientificName": 1, "familyCommonName": 1, "edible": 1,"genus":1,"imageURL":1}))
        common_name = request.args.get('commonName', '')
        sapling_desc = request.args.get('saplingDescription', '')
        request_id = request.args.get('request_id', '')
        print('request id is', request_id)
        
        return render_template('admin.html', commonName=common_name, saplingDescription=sapling_desc)

    # If it's a POST request, handle the plant addition
    if  request.method == 'POST':

        if not request.is_json:
            return jsonify({"error": "Invalid content type, expected JSON"}), 415  # Ensure JSON format
        data = request.json  # Expecting JSON data
        print('data is ',data)

        new_plant = {
            "commonName": data.get('commonName'),
            "scientificName": data.get('scientificName'),
            "rank": data.get('rank'),
            "familyCommonName": data.get('familyCommonName'),
            "genus": data.get('genus'),
            "imageURL": data.get('imageURL'),
            "edible": data.get('edible', False),
            "saplingDescription": data.get('saplingDescription')
        }

          
        db.plants.insert_one(new_plant)
        #delete pending plant request
        request_id = request.args.get('request_id')
        if request_id:
            db.plant_requests.delete_one({"_id": ObjectId(request_id)})

        # 🔔 Send Email Notification
        # Assuming you know which user to notify — get their details from the request or DB
        user_id = data.get('user_id')  # Make sure this comes from the frontend
        user = db.users.find_one({"_id": ObjectId(user_id)})

        if user:
            subject = f"New Plant Added to Your Garden: {new_plant['commonName']}"
            body = f"""
                    Hello {user['full_name']},

                    A new plant has been added to your garden:

                    🌱 Common Name: {new_plant['commonName']}
                    🔬 Scientific Name: {new_plant['scientificName']}
                    🌿 Family: {new_plant['familyCommonName']}
                    📷 Image: {new_plant['imageURL']}
                    📖 Description: {new_plant['saplingDescription']}

                    Happy Gardening! 🌼

                    - Garden Team
                    """
            send_email_task.delay(
                subject=subject,
                recipients=[user['email']],
                body=body
            )

        return jsonify({"message": "Plant added and user notified successfully!"})     


@dashboard_bp.route('/edit_plant/<plant_id>', methods=['PUT'])
@login_required
def edit_plant(plant_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    data = request.json
    db = current_app.config['DB_CONNECTION']
    update_data = {
        "commonName": data.get("commonName"),
        "scientificName": data.get("scientificName"),
        "rank": data.get("rank"),
        "familyCommonName": data.get("familyCommonName"),
        "genus": data.get("genus"),
        "imageURL": data.get("imageURL"),
        "edible": data.get("edible"),
        "saplingDescription": data.get("saplingDescription")
    }

    db.plants.update_one({"_id": ObjectId(plant_id)}, {"$set": update_data})
    return jsonify({"message": "Plant updated successfully!"})

@dashboard_bp.route("/get_plant/<plant_id>", methods=["GET"])
@login_required
def get_plant(plant_id):
    db = current_app.config['DB_CONNECTION']
    plant = db.plants.find_one({"_id": ObjectId(plant_id)})
    if not plant:
        return jsonify({"error": "Plant not found"}), 404

    plant["_id"] = str(plant["_id"])  # Convert ObjectId to string for JSON response
    return jsonify(plant)

@dashboard_bp.route('/request_plant', methods=['GET', 'POST'])
@login_required
def request_plant():
    db = current_app.config['DB_CONNECTION']

    if request.method == 'GET':
        return render_template('request_plant.html')

    # Handle form submission
    plant_name = request.form.get("plantName", "").strip()
    plant_description = request.form.get("plantDescription", "").strip()

    if not plant_name:
        flash("Plant name is required!", "danger")
        return redirect(url_for('dashboard.request_plant'))

    # Check if the plant already exists in the main plants database
    existing_plant = db.plants.find_one({"commonName": {"$regex": f"^{plant_name}$", "$options": "i"}})

    if existing_plant:
        flash("This plant is already available in the database!", "warning")
        return redirect(url_for('dashboard.request_plant'))

    # Insert request into database if plant doesn't exist
    db.plant_requests.insert_one({
        "plantName": plant_name,
        "description": plant_description,
        "user_id": ObjectId(current_user.id),
        "status": "pending",
        "requested_at": datetime.now()
    })

    flash("Your plant request has been submitted for approval!", "success")
    return redirect(url_for('dashboard.dashboard'))


@dashboard_bp.route('/admin/pending_plants', methods=['GET'])
@login_required
def pending_plants():
    if current_user.role != "admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    db = current_app.config['DB_CONNECTION']
    pending_requests = list(db.plant_requests.find({"status": "pending"}))

    if not pending_requests:
        flash("No pending plant requests!", "info")
        return redirect(url_for('dashboard.dashboard'))

    return render_template('pending_plants.html', pending_requests=pending_requests)

@dashboard_bp.route('/admin/approve_plant/<request_id>', methods=['POST'])
@login_required
def approve_plant(request_id):
    if current_user.role != "admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    db = current_app.config['DB_CONNECTION']
    plant_request = db.plant_requests.find_one({"_id": ObjectId(request_id)})

    if plant_request:
        
        # Redirect to the Add Plant form with prefilled details
        return redirect(url_for('dashboard.add_plant', 
                                request_id=request_id,
                                commonName=plant_request["plantName"], 
                                saplingDescription=plant_request.get("description", "")))

    flash("Plant request not found!", "danger")
    return redirect(url_for('dashboard.pending_plants'))


@dashboard_bp.route('/admin/reject_plant/<request_id>', methods=['POST'])
@login_required
def reject_plant(request_id):
    if current_user.role != "admin":
        flash("Unauthorized access!", "danger")
        return redirect(url_for('dashboard.dashboard'))

    db = current_app.config['DB_CONNECTION']
    db.plant_requests.delete_one({"_id": ObjectId(request_id)})
    flash("Plant request rejected!", "danger")

    return redirect(url_for('dashboard.pending_plants'))

@dashboard_bp.route('/delete_garden/<garden_id>',methods=['DELETE'])
@login_required
def delete_garden(garden_id):
    try:
        db=current_app.config['DB_CONNECTION']
        garden=db.garden.find_one({"_id":ObjectId(garden_id),"user_id":ObjectId(current_user.id)})
        if not garden:
            return jsonify({"success":False,"message":"Garden not found"}),403
        db.garden.delete_one({"_id":ObjectId(garden_id),"user_id":ObjectId(current_user.id)})
        db.garden_plant.delete_many({"garden_id":ObjectId(garden_id)})
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"messege":str(e)}),500