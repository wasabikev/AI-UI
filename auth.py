# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, db

auth = Blueprint('auth', __name__)

@auth.route('/admin')
@login_required  # Ensure only logged-in users can access this route
def admin_dashboard():
    users = User.query.all()  # Fetch all users from the database
    return render_template('admin.html', users=users)

@auth.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required  # Ensure only logged-in users can perform this action
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('auth.admin_dashboard'))

# ... Rest of your existing auth routes ...



@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the username and password from the form
        username = request.form.get('username')
        password = request.form.get('password')

        # Query your User model to find the user by username
        user = User.query.filter_by(username=username).first()

        # Check if the user exists and the password is correct
        if user and check_password_hash(user.password_hash, password):
            # Log the user in
            login_user(user)
            # Redirect to the home page or other appropriate page
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    # Log the user out
    logout_user()
    # Redirect to home page or login page
    return redirect(url_for('home'))

@auth.route('/register', methods=['GET', 'POST'])
def register():
    print("Register route accessed")  # Debugging print statement
    if request.method == 'POST':
        # Collect user information from form
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if username already exists
        user_by_username = User.query.filter_by(username=username).first()
        if user_by_username:
            flash('Username already exists')
            return redirect(url_for('auth.register'))

        # Check if email already exists
        user_by_email = User.query.filter_by(email=email).first()
        if user_by_email:
            flash('Email already in use. Please use a different email.')
            return redirect(url_for('auth.register'))

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Create new user instance
        new_user = User(username=username, email=email, password_hash=hashed_password)

        # Add new user to the database
        db.session.add(new_user)
        db.session.commit()

        # Redirect to the login page, or possibly log the user in directly
        return redirect(url_for('auth.login'))

    return render_template('register.html')
