from celery import shared_task
from flask_mail import Message,Mail
from flask import current_app,Flask
from app import mail
from app.config import Config
from app.celery_app import celery
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo import MongoClient

app = Flask(__name__)
app.config.from_object(Config)

mail = Mail(app)
def get_mongo_collection():
    client = MongoClient(current_app.config['MONGO_URI'])
    db = client.get_default_database()
    return db['user_plants'], db['users']



def create_flask_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    mail = Mail(app)
    return app, mail

@celery.task(name='send_email_task')  # Explicit name avoids import issues
def send_email_task(subject, recipients, body):
    app, mail = create_flask_app()
    print('app and mail is ', app ,'   ',mail) 
    with app.app_context():
        msg = Message(subject=subject,
                      sender=app.config['MAIL_USERNAME'],
                      recipients=recipients,
                      body=body)
        mail.send(msg)

@shared_task
def send_plant_added_email(user_email, plant_name):
    """Send confirmation email when a plant is added."""
    with current_app.app_context():
        msg = Message(
            subject="Plant Added to Your Garden!",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[user_email],
            body=f"Hello,\n\nThe plant '{plant_name}' has been successfully added to your garden. Happy gardening!\n\nBest Regards,\nGardening Companion Team"
        )
        mail.send(msg)

@shared_task
def send_periodic_email(user_email, plant_name):
    """Send a periodic plant reminder."""
    with current_app.app_context():
        msg = Message(
            subject="Plant Reminder",
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[user_email],
            body=f"Hello,\n\nYour plant '{plant_name}' is still active in your garden.\n\nBest,\nGardening Companion"
        )
        mail.send(msg)

@shared_task
def send_fertilizer_notifications():
    """Send fertilizer reminders to users whose plants are due."""
    plants_col, users_col = get_mongo_collection()
    now = datetime.utcnow()

    due_plants = plants_col.find({
        "$expr": {
            "$lte": [
                {"$add": ["$created_at", {"$multiply": ["$fertilizing", 86400000]}]},
                now
            ]
        }
    })

    for plant in due_plants:
        user = users_col.find_one({"_id": ObjectId(plant['user_id'])})
        if user:
            send_email_task(user['email'], f"Fertilizer Reminder for {plant['name']}",
                       f"Hi, it's time to fertilize your plant '{plant['name']}'. Please do so today!")

@shared_task
def send_watering_notifications():
    """Send watering reminders to users whose plants are due."""
    plants_col, users_col = get_mongo_collection()
    now = datetime.utcnow()

    due_plants = plants_col.find({
        "$expr": {
            "$lte": [
                {"$add": ["$created_at", {"$multiply": ["$watering", 86400000]}]},
                now
            ]
        }
    })

    for plant in due_plants:
        user = users_col.find_one({"_id": ObjectId(plant['user_id'])})
        if user:
            send_email_task(user['email'], f"Watering Reminder for {plant['name']}",
                       f"Hi, it's time to water your plant '{plant['name']}'. Don't forget!")

@shared_task
def send_repotting_notifications():
    """Send repotting reminders to users whose plants are due."""
    plants_col, users_col = get_mongo_collection()
    now = datetime.utcnow()

    due_plants = plants_col.find({
        "$expr": {
            "$lte": [
                {"$add": ["$created_at", {"$multiply": ["$repotting", 86400000]}]},
                now
            ]
        }
    })

    for plant in due_plants:
        user = users_col.find_one({"_id": ObjectId(plant['user_id'])})
        if user:
            send_email_task(user['email'], f"Repotting Reminder for {plant['name']}",
                       f"Hi, it's time to repot your plant '{plant['name']}'. Make sure it has space to grow!")



# def send_email(recipient, subject, body):
#     """Helper function to send email."""
#     with current_app.app_context():
#         msg = Message(subject=subject, recipients=[recipient], body=body)
#         mail.send(msg)

