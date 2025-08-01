from kafka import KafkaConsumer
from app.tasks import send_email_task  # your existing Celery task
import json

def start_email_consumer():
    consumer = KafkaConsumer(
        'email-topic',
        bootstrap_servers='localhost:9092',
        group_id='email-group',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True
    )

    print("📩 Kafka email consumer started. Listening for events...")

    for message in consumer:
        data = message.value
        print("📨 Email task received from Kafka:", data)
        # Pass it to Celery
        send_email_task.delay(
            subject=data['subject'],
            recipients=data['recipients'],
            body=data['body']
        )

if __name__ == "__main__":
    start_email_consumer()
