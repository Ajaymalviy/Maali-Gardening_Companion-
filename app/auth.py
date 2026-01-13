import os
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app,jsonify,session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from flask_mail import Message
from .models import User
from . import mail
import requests
from .utils import generate_reset_token, verify_reset_token
import app.config
auth = Blueprint('auth', __name__)

# Regex patterns
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
PASSWORD_REGEX = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@#_]{8,}$'
PHONE_REGEX = r'^\+?[0-9]{10,15}$'
USERNAME_REGEX = r'^[A-Za-z][A-Za-z0-9_]{4,29}$'

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


# ---------- GOOGLE OAUTH ROUTES ----------
@auth.route('/login/now')
def google_login():
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    request_uri = (
        authorization_endpoint + 
        "?response_type=code" +
        f"&client_id={'745426787344-1o3tnk39j9s84vtif2gbn8v277e0ks6r.apps.googleusercontent.com'}" +
        f"&redirect_uri={url_for('auth.callback', _external=True)}" +
        "&scope=openid%20email%20profile"
    )

    return redirect(request_uri)


@auth.route('/login/callback')
def callback():
    try:
        print(' ia m in try')
        code = request.args.get("code")
        print(
            'code is something like ', code
        )
        if not code:
            flash("Authorization code not provided", "danger")
            return redirect(url_for("auth.login"))

        google_provider_cfg = get_google_provider_cfg()
        print('google provider ', google_provider_cfg)
        token_endpoint = google_provider_cfg["token_endpoint"]
        print('tocken endlpint', token_endpoint)
        token_response = requests.post(
            token_endpoint,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "code": code,
                "client_id": '745426787344-1o3tnk39j9s84vtif2gbn8v277e0ks6r.apps.googleusercontent.com',
                "client_secret": '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',
                "redirect_uri": url_for('auth.callback', _external=True),
                "grant_type": "authorization_code"
            },
        )

        token_json = token_response.json()
        print('token_json', token_json)
        access_token = token_json.get("access_token")
        print('access token', access_token)

        # Fetch user info from Google
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        print('userinfo endpoint', userinfo_endpoint)
        userinfo_response = requests.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info = userinfo_response.json()
        print("userinfo", user_info)

        # Extract relevant user fields
        email = user_info.get("email")
        full_name = user_info.get("name")
        username = user_info.get("given_name")
        profile_pic = user_info.get("picture", "")
        print(f"whole detail like email = { email} , full name  = {full_name} , username =  {username } and profile_pic =  {profile_pic}")

        if not email:
            flash("No email found in Google account.", "danger")
            return redirect(url_for("auth.login"))

        # Find or create user in your app's DB
        user = User.find_by_email(email)
        print('user is ',user)
        if not user:
            user_id = User.create_user(
                full_name=full_name,
                username=username,
                email=email,
                password=None,
                phone_no=None,
                role="user",
                status="active",
                profile_pic=profile_pic
            )
            phone_no = None
            user = User.find_by_email(email)
   
        else:
            user_id = str(user['_id'])
            phone_no = user.get('phone_no')
            full_name = user.get('full_name', full_name)
            username = user.get('username', username)

        user_id_str = str(user_id)
        print('useridstring is ',user_id_str)
        # Create app user session
        user_obj = User(
            id=user_id_str,
            email=email,
            username=username,
            full_name=full_name,
            phone_no=phone_no,
            role=user.get('role', 'user')
        )
        print(f"Type of user_obj.id: {type(user_obj.id)}, Value: {user_obj.id}") # Inspect the id
        print("Before login_user:", user_obj.__dict__)
        login_user(user_obj)
        print("After login_user:", current_user)
        if not phone_no:
            flash("Please update your phone number.", "info")
            return redirect(url_for("auth.update_phone"))

        flash("Login successful!", "success")
        return redirect(url_for("dashboard.dashboard"))

    except Exception as e:
        print(f"Google Auth Error: {e}")
        flash("Google login failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))


# ---------- LOCAL AUTH ROUTES ----------
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        if not identifier or not password:
            flash('Please provide both username/email/phone and password.', 'danger')
            return redirect(url_for('auth.login'))

        # Use User model method
        user = User.find_by_identifier(identifier)

        if not user:
            flash('Username or email not found.', 'danger')
            return redirect(url_for('auth.login'))

        if not User.check_password(user, password):
            flash('Incorrect password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        # Create user object for login
        user_obj = User(
            id=str(user['_id']),
            full_name=user['full_name'],
            username=user['username'],
            email=user['email'],
            phone_no=user.get('phone_no'),
            role=user.get('role', 'user')
        )
        login_user(user_obj)

        return redirect(url_for('dashboard.dashboard'))

    return render_template('login.html')

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone_no = request.form['phone_no']

        # Validation
        if not re.match(EMAIL_REGEX, email):
            flash('Invalid email format.', 'danger')
        elif not re.match(PASSWORD_REGEX, password):
            flash('Password must be at least 8 characters long and contain at least one letter and one number.', 'danger')
        elif not re.match(PHONE_REGEX, phone_no):
            flash('Invalid phone number.', 'danger')
        elif not re.match(USERNAME_REGEX, username):
            flash("Invalid username. Must start with a letter and contain only letters, numbers, and underscores (5-30 chars).", "danger")
        else:
            # Check for existing users using model methods
            if User.find_by_email(email):
                flash('Email is already registered.', 'danger')
            elif User.find_by_username(username):
                flash('Username is already taken.', 'danger')
            elif User.find_by_phone_no(phone_no):
                flash('Phone number is already taken.', 'danger')
            else:
                # Create user through User model
                User.create_user(
                    full_name=full_name,
                    username=username,
                    email=email,
                    password=password,
                    phone_no=phone_no
                )
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('auth.login'))

    return render_template('signup.html')

@auth.route("/update_phone", methods=["GET", "POST"])
@login_required
def update_phone():
    user = User.find_by_email(current_user.email)

    if request.method == "POST":
        username = request.form.get("username")
        phone_no = request.form.get("phone_no")
        full_name = request.form.get("full_name")

        # Validation
        if not username or not re.match(USERNAME_REGEX, username):
            flash("Invalid username.", "danger")
        elif User.username_exists(username, exclude_email=current_user.email):
            flash("Username is already taken.", "danger")
        elif not phone_no or not re.match(PHONE_REGEX, phone_no):
            flash("Invalid phone number format.", "danger")
        elif User.phone_no_exists(phone_no, exclude_email=current_user.email):
            flash("Phone number is already in use.", "danger")
        elif not full_name or len(full_name) < 3:
            flash("Full name must be at least 3 characters long.", "danger")
        else:
            # Update user through User model
            User.update_user(
                user_id=str(user['_id']),
                updates={
                    "username": username,
                    "phone_no": phone_no,
                    "full_name": full_name
                }
            )
            flash("Profile updated successfully!", "success")
            return redirect(url_for("dashboard.dashboard"))

    return render_template("update_phone.html", user=user)

@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = User.find_by_email(email)
        
        if user:
            token = generate_reset_token(email)
            reset_link = url_for("auth.reset_password", token=token, _external=True)

            msg = Message("Password Reset Request", 
                         sender="your_email@gmail.com", 
                         recipients=[email])
            msg.body = f"Click the link to reset your password: {reset_link}"
            msg.html = f"""
                <p>Click the link below to reset your password:</p>
                <p><a href="{reset_link}" target="_blank"><strong>Reset Password</strong></a></p>
                <p>If you did not request this, please ignore this email.</p>
            """

            try:
                mail.send(msg)
                flash("A password reset link has been sent to your email.", "info")
            except Exception as e:
                print(f"Email send error: {e}")
                flash("Error sending email. Try again later.", "danger")
        else:
            flash("Email not found.", "danger")

    return render_template("forgot_password.html")

@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("Invalid or expired token.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if not re.match(PASSWORD_REGEX, new_password):
            flash('Password must be at least 8 characters long and contain at least one letter and one number.', 'danger')
        elif new_password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            # Update password through User model
            User.update_password(email, new_password)
            flash("Your password has been updated! Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have successfully logged out.', 'success')
    return redirect(url_for('auth.login'))