# auth.py
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, db
from datetime import datetime, timedelta

import logging

# Retrieve master admin credentials from environment variables
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

auth = Blueprint('auth', __name__)

@auth.route('/update-password/<int:user_id>', methods=['POST'])
@login_required
def update_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('newPassword')
    # Hash the new password and update the user record
    # ... your logic to update the password ...
    db.session.commit()
    flash('Password updated successfully', 'success')
    return redirect(url_for('auth.admin_dashboard'))

@auth.route('/update-admin/<int:user_id>', methods=['POST'])
@login_required
def update_admin(user_id):
    user = User.query.get_or_404(user_id)
    # Toggle the admin status
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(f"Admin status for {user.username} updated to {'admin' if user.is_admin else 'non-admin'}.", 'success')
    return redirect(url_for('auth.admin_dashboard'))

@auth.route('/update-status/<int:user_id>', methods=['POST'])
@login_required
def update_status(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.status = request.form.get('status')
        db.session.commit()
        flash('User status updated successfully', 'success')
    
    return redirect(url_for('auth.admin_dashboard'))

@auth.route('/admin')
@login_required
def admin_dashboard():
    users = User.query.order_by(User.username).all()  # Fetch all users and order them by username
    return render_template('admin.html', users=users, timedelta=timedelta)

@auth.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required  # Ensure only logged-in users can perform this action
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('auth.admin_dashboard'))

@auth.route('/update-user/<int:user_id>', methods=['POST'])
@login_required  # Ensure only logged-in users can perform this action
def update_user(user_id):
    user = User.query.get_or_404(user_id)

    # Implement the logic to update user details
    if request.method == 'POST':
        user.username = request.form.get('username', user.username)
        user.email = request.form.get('email', user.email)
        user.is_admin = 'is_admin' in request.form  # Checkbox for admin status
        user.status = request.form.get('status', user.status)
        
        # If password field is not empty, update password
        password = request.form.get('password')
        if password:
            user.password_hash = generate_password_hash(password)

        db.session.commit()
        flash('User updated successfully', 'success')
    
    return redirect(url_for('auth.admin_dashboard'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            try:
                user.last_login = datetime.utcnow()
                db.session.commit()
                logging.info(f"Updated last login for user {username}")
            except Exception as e:
                logging.error(f"Error updating last login for user {username}: {e}")

            login_user(user)
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
