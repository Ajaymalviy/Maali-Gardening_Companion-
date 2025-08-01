from flask import Blueprint, request
from app.tasks import send_email_task

done = Blueprint('done', __name__)

@done.route('/send-email', methods=['POST'])
def send_email():
    print('i m in send mail')
    data = request.get_json()
    print('data is ', data)
    send_email_task.delay(
        subject=data['subject'],
        recipients=data['recipients'],
        body=data['body']
    )
    return {'status': 'Email is being sent'}, 202
