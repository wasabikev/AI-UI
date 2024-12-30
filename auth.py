# auth.py
__all__ = ['auth_bp', 'init_auth', 'UserWrapper', 'async_login_required']

from functools import wraps
from quart import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from quart_auth import (
    QuartAuth,
    AuthUser,
    current_user,
    login_required,
    login_user,
    logout_user
)
from werkzeug.security import generate_password_hash
from models import User, get_session
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional, Callable, Any, TypeVar, cast

auth_bp = Blueprint('auth', __name__)

# Initialize auth
auth_manager = QuartAuth() 

# Type variable for better type hinting
RouteCallable = TypeVar('RouteCallable', bound=Callable[..., Any])

class UserWrapper(AuthUser):
    def __init__(self, auth_id: str):
        super().__init__(auth_id)
        self._user: Optional[User] = None
        self._auth_id = auth_id

    @property
    def is_authenticated(self) -> bool:
        """Synchronous property required by Quart-Auth"""
        return bool(self._auth_id)

    @property
    def id(self) -> int:
        """Property to access the user ID"""
        return int(self._auth_id) if self._auth_id else None

    async def get_user(self) -> Optional[User]:
        """Async method to load and return user data"""
        if self._user is None and self._auth_id is not None:
            try:
                async with get_session() as session:
                    result = await session.execute(
                        select(User).filter(User.id == int(self._auth_id))
                    )
                    self._user = result.scalar_one_or_none()
            except Exception as e:
                current_app.logger.error(f"Error retrieving user: {str(e)}")
                return None
        return self._user

    def get_auth_id(self) -> str:
        """Required by Quart-Auth"""
        return str(self._auth_id)

    @property
    async def is_admin(self) -> bool:
        """Async property to get admin status"""
        user = await self.get_user()
        return bool(user and user.is_admin)

    async def check_admin(self) -> bool:
        """Utility method to check admin status"""
        return await self.is_admin
    
def login_required(func: RouteCallable) -> RouteCallable:
    """
    Drop-in replacement for Quart-Auth's login_required decorator.
    Use this instead of importing login_required from quart_auth.
    """
    @wraps(func)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        # Use synchronous check for authentication status
        if not current_user or not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for("auth.login"))
        
        # Then do async user check
        try:
            user = await current_user.get_user()
            if user is None or user.status != 'Active':
                if request.is_json:
                    return jsonify({'error': 'Unauthorized'}), 401
                return redirect(url_for("auth.login"))
        except Exception as e:
            current_app.logger.error(f"Error checking user status: {str(e)}")
            if request.is_json:
                return jsonify({'error': 'Authentication error'}), 401
            return redirect(url_for("auth.login"))
                
        return await func(*args, **kwargs)
    return cast(RouteCallable, wrapped)
        
def async_login_required():
    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            authenticated = await current_user.check_authenticated()
            if not authenticated:
                return redirect(url_for('auth.login'))
                
            return await f(*args, **kwargs)
        return decorated_function
    return decorator

def init_auth(app):
    auth_manager.user_class = UserWrapper
    auth_manager.init_app(app)

@auth_bp.route('/update-password/<int:user_id>', methods=['POST'])
@async_login_required()
async def update_password(user_id):
    async with get_session() as session:
        result = await session.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await flash('User not found', 'error')
            return redirect(url_for('auth.admin_dashboard'))
            
        form = await request.form
        new_password = form.get('newPassword')
        user.set_password(new_password)
        await session.commit()
        
    await flash('Password updated successfully', 'success')
    return redirect(url_for('auth.admin_dashboard'))

@auth_bp.route('/update-admin/<int:user_id>', methods=['POST'])
@async_login_required()
async def update_admin(user_id):
    async with get_session() as session:
        result = await session.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await flash('User not found', 'error')
            return redirect(url_for('auth.admin_dashboard'))
            
        user.is_admin = not user.is_admin
        await session.commit()
        
    await flash(f"Admin status for {user.username} updated to {'admin' if user.is_admin else 'non-admin'}.", 'success')
    return redirect(url_for('auth.admin_dashboard'))

@auth_bp.route('/update-status/<int:user_id>', methods=['POST'])
@async_login_required()
async def update_status(user_id):
    async with get_session() as session:
        result = await session.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await flash('User not found', 'error')
            return redirect(url_for('auth.admin_dashboard'))
            
        form = await request.form
        user.status = form.get('status')
        await session.commit()
        
    await flash('User status updated successfully', 'success')
    return redirect(url_for('auth.admin_dashboard'))

@auth_bp.route('/admin')
@async_login_required()
async def admin_dashboard():
    current_user_obj = await current_user.get_user()
    
    if not current_user_obj.is_admin:
        await flash("Sorry, you do not have permission to access the admin dashboard.", "danger")
        return redirect(url_for('home'))

    async with get_session() as session:
        result = await session.execute(
            select(User).order_by(User.username)
        )
        users = result.scalars().all()
    
    return await render_template('admin.html', users=users)

@auth_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@async_login_required()
async def delete_user(user_id):
    async with get_session() as session:
        result = await session.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            await session.delete(user)
            await session.commit()
            await flash('User deleted successfully', 'success')
        else:
            await flash('User not found', 'error')
    return redirect(url_for('auth.admin_dashboard'))


@auth_bp.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        form = await request.form
        username = form.get('username')
        password = form.get('password')
        
        async with get_session() as session:
            try:
                result = await session.execute(
                    select(User).filter(User.username == username)
                )
                user = result.scalar_one_or_none()

                if user and user.check_password(password):
                    if user.status != 'Active':
                        await flash('Account is not active. Please contact administrator.', 'warning')
                        return redirect(url_for('auth.login'))

                    try:
                        # Use naive datetime to match the schema
                        current_time = datetime.utcnow()
                        user.last_login = current_time
                        user.updated_at = current_time
                        await session.commit()
                    except Exception as e:
                        current_app.logger.error(f"Error updating user timestamps: {str(e)}")
                        await session.rollback()
                    
                    # Create auth user and login
                    auth_user = UserWrapper(str(user.id))
                    login_user(auth_user)
                    
                    return redirect(url_for('home'))
                
            except Exception as e:
                current_app.logger.error(f"Error during login process: {str(e)}")
                await session.rollback()
            
        await flash('Invalid username or password', 'danger')
    
    return await render_template('login.html')

@auth_bp.route('/logout')
@async_login_required()
async def logout():
    logout_user()
    return redirect(url_for('home'))

@auth_bp.route('/register', methods=['GET', 'POST'])
async def register():
    if request.method == 'POST':
        form = await request.form
        username = form.get('username')
        email = form.get('email')
        password = form.get('password')

        async with get_session() as session:
            # Check existing username
            result = await session.execute(
                select(User).filter(User.username == username)
            )
            if result.scalar_one_or_none():
                await flash('Username already exists')
                return redirect(url_for('auth.register'))

            # Check existing email
            result = await session.execute(
                select(User).filter(User.email == email)
            )
            if result.scalar_one_or_none():
                await flash('Email already in use. Please use a different email.')
                return redirect(url_for('auth.register'))

            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password)
            )

            session.add(new_user)
            await session.commit()

        await flash('Your account has been created and is pending approval. You will receive an email once it is activated.', 'info')
        return redirect(url_for('auth.login'))

    return await render_template('register.html')