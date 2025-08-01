##routes.py##
from flask import render_template, Blueprint, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.tasks import send_email_task

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/tips_tricks')
def tips_tricks():
    return render_template('tips_tricks.html')


