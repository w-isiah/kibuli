from flask import (
    render_template, redirect, request, url_for, flash, session, current_app, jsonify
)
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from PIL import Image
import os
import uuid
import time
import mysql.connector
import pytz

from apps import get_db_connection
from apps.authentication import blueprint
from apps.utils.decorators import login_required

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_kampala_time():
    """Get current time in Kampala timezone"""
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def update_user_logout(user_id, connection):
    """Helper function to update user logout status"""
    try:
        with connection.cursor(dictionary=True) as cursor:
            current_time = get_kampala_time()
            current_time_naive = current_time.replace(tzinfo=None)
            
            cursor.execute("""
                UPDATE user_activity 
                SET logout_time = %s 
                WHERE user_id = %s AND logout_time IS NULL
            """, (current_time_naive, user_id))
            
            cursor.execute("UPDATE users SET is_online = 0 WHERE id = %s", (user_id,))
            connection.commit()
            return True
    except Exception as e:
        print(f"Error updating user logout: {e}")
        return False

def handle_profile_image(profile_image, user_id=None, crop_data=None):
    """Handle profile image upload with cropping"""
    if not profile_image or not allowed_file(profile_image.filename):
        return None
    
    # Create unique filename
    if user_id:
        filename = f"user_{user_id}_{int(time.time())}.png"
    else:
        filename = f"new_user_{int(time.time())}.png"
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    try:
        img = Image.open(profile_image)
        
        # Apply crop if coordinates provided
        if crop_data:
            try:
                x = float(crop_data.get('x', 0))
                y = float(crop_data.get('y', 0))
                w = float(crop_data.get('w', 0))
                h = float(crop_data.get('h', 0))
                
                if w > 0 and h > 0:
                    img = img.crop((x, y, x + w, y + h))
            except (ValueError, TypeError):
                pass
        
        img.save(file_path)
        return filename
    except Exception as e:
        print(f"Error processing profile image: {e}")
        return None

def handle_sign_image(sign_image, user_id=None, crop_data=None):
    """Handle signature image upload with cropping"""
    if not sign_image or not allowed_file(sign_image.filename):
        return None
    
    # Create unique filename
    timestamp = int(time.time())
    filename = f"sign_{user_id if user_id else 'new'}_{timestamp}.png"
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    try:
        img = Image.open(sign_image)
        
        # Apply crop if coordinates provided
        if crop_data:
            try:
                x = float(crop_data.get('x', 0))
                y = float(crop_data.get('y', 0))
                w = float(crop_data.get('w', 0))
                h = float(crop_data.get('h', 0))
                
                if w > 0 and h > 0:
                    img = img.crop((x, y, x + w, y + h))
            except (ValueError, TypeError):
                pass
        
        img.save(file_path, "PNG")
        return filename
    except Exception as e:
        print(f"Error processing signature image: {e}")
        return None

def get_user_by_id(user_id, connection):
    """Fetch user by ID"""
    with connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()

def user_has_role(required_roles):
    """Decorator for role-based access control"""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role')
            if user_role not in required_roles:
                flash('Access Denied: Insufficient Permissions.', 'warning')
                return redirect(url_for('home_blueprint.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============================================
# ROUTES
# ============================================

@blueprint.route('/', methods=['GET', 'POST'])
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('accounts/login.html')
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                    user = cursor.fetchone()
                    
                    if not user:
                        flash('Username not found.', 'danger')
                        return render_template('accounts/login.html')
                    
                    # Password comparison (plaintext as requested)
                    if user['password'] != password:
                        flash('Incorrect password.', 'danger')
                        return render_template('accounts/login.html')
                    
                    # Record login
                    login_time = get_kampala_time()
                    login_time_naive = login_time.replace(tzinfo=None)
                    
                    cursor.execute(
                        "INSERT INTO user_activity (user_id, login_time) VALUES (%s, %s)",
                        (user['id'], login_time_naive)
                    )
                    cursor.execute(
                        "UPDATE users SET is_online = 1 WHERE id = %s",
                        (user['id'],)
                    )
                    
                    # Generate session token
                    session_token = str(uuid.uuid4())
                    session['token'] = session_token
                    cursor.execute(
                        "UPDATE users SET session_token = %s WHERE id = %s",
                        (session_token, user['id'])
                    )
                    
                    conn.commit()
                    
                    # Set session data
                    session.update({
                        'loggedin': True,
                        'id': user['id'],
                        'username': user['username'],
                        'assigned_db': user.get('assigned_db'),
                        'profile_image': user.get('profile_image'),
                        'first_name': user.get('first_name'),
                        'role': user.get('role'),
                        'role1': user.get('role1'),
                        'last_activity': login_time.isoformat()
                    })
                    
                    session.permanent = False
                    
                    flash(f"Login successful! Connected to {session['assigned_db']}", 'success')
                    return redirect(url_for('home_blueprint.index'))
                    
        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'danger')
    
    return render_template('accounts/login.html')

@blueprint.before_app_request
def check_token_validity():
    """Check if session token is still valid"""
    if 'loggedin' in session:
        user_id = session.get('id')
        token = session.get('token')
        
        try:
            with get_db_connection() as connection:
                with connection.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT session_token FROM users WHERE id = %s", (user_id,))
                    result = cursor.fetchone()
                    
                    if result and token != result['session_token']:
                        session.clear()
                        flash('You were logged out by an administrator.', 'info')
                        return redirect(url_for('authentication_blueprint.login'))
        except Exception as e:
            print(f"Token validation error: {e}")
            session.clear()
            return redirect(url_for('authentication_blueprint.login'))

@blueprint.before_app_request
def check_inactivity():
    """Check for session timeout due to inactivity"""
    if 'loggedin' in session:
        last_activity_str = session.get('last_activity')
        if last_activity_str:
            try:
                last_activity = datetime.fromisoformat(last_activity_str)
                current_time = get_kampala_time()
                
                # Timeout after 30 minutes
                if (current_time - last_activity) > timedelta(minutes=30):
                    try:
                        with get_db_connection() as connection:
                            update_user_logout(session['id'], connection)
                        session.clear()
                        flash('Session expired due to inactivity.', 'warning')
                        return redirect(url_for('authentication_blueprint.login'))
                    except Exception as e:
                        print(f"Inactivity logout error: {e}")
                        session.clear()
                        return redirect(url_for('authentication_blueprint.login'))
            except Exception:
                pass
        
        # Update last activity
        session['last_activity'] = get_kampala_time().isoformat()

@blueprint.route('/logout')
def logout():
    """User logout"""
    user_id = session.get('id')
    username = session.get('username')
    
    if user_id:
        try:
            with get_db_connection() as connection:
                update_user_logout(user_id, connection)
                print(f"User '{username}' logged out successfully.")
        except Exception as e:
            print(f"Logout error: {e}")
            flash(f"An error occurred during logout: {str(e)}", 'danger')
    
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('authentication_blueprint.login'))

@blueprint.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration"""
    if request.method == 'POST':
        # Collect form data
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        
        # Validation
        if not all([username, password, first_name, last_name, email]):
            flash('Please fill in all required fields.', 'danger')
            return render_template('accounts/signup.html')
        
        try:
            with get_db_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:
                    # Check existing username
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    if cursor.fetchone():
                        flash('Username already exists.', 'danger')
                        return render_template('accounts/signup.html')
                    
                    # Check existing email
                    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cursor.fetchone():
                        flash('Email address is already in use.', 'danger')
                        return render_template('accounts/signup.html')
                    
                    # Insert new user
                    cursor.execute("""
                        INSERT INTO users (
                            username, password, role, first_name, last_name,
                            email, phone_number, is_online
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                    """, (username, password, 'applicant', first_name, last_name, email, phone_number))
                    
                    conn.commit()
                    flash('Account created successfully. Please sign in.', 'success')
                    return redirect(url_for('authentication_blueprint.login'))
                    
        except Exception as e:
            flash('An error occurred during registration.', 'danger')
            print(f"Signup error: {e}")
    
    return render_template('accounts/signup.html')

@login_required
@blueprint.route('/force_logout/<int:user_id>')
@user_has_role(['admin', 'super_admin'])
def force_logout(user_id):
    """Force logout a specific user"""
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                current_time = get_kampala_time().replace(tzinfo=None)
                
                # Update user activity
                cursor.execute("""
                    UPDATE user_activity
                    SET logout_time = %s
                    WHERE user_id = %s AND logout_time IS NULL
                    ORDER BY login_time DESC
                    LIMIT 1
                """, (current_time, user_id))
                
                cursor.execute("UPDATE users SET is_online = 0 WHERE id = %s", (user_id,))
                
                # Invalidate session
                new_token = str(uuid.uuid4())
                cursor.execute("UPDATE users SET session_token = %s WHERE id = %s", (new_token, user_id))
                
                connection.commit()
                flash("User has been signed out successfully.", "success")
    except Exception as e:
        flash(f"Error during forced logout: {str(e)}", "danger")
    
    return redirect(url_for('authentication_blueprint.manage_users'))

@login_required
@blueprint.route('/manage_users')
@user_has_role(['super_admin', 'admin', 'inventory_manager'])
def manage_users():
    """Manage users page with RBAC filtering"""
    current_user_role = session.get('role')
    
    # RBAC hierarchy
    excluded_roles_map = {
        'super_admin': ['super_admin'],
        'admin': ['admin', 'super_admin'],
        'inventory_manager': ['admin', 'inventory_manager', 'super_admin', 'class_teacher']
    }
    
    excluded_roles = excluded_roles_map.get(current_user_role, ['admin', 'super_admin'])
    
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                placeholders = ','.join(['%s'] * len(excluded_roles))
                query = f"""
                    SELECT 
                        u.id, u.username, u.role, u.name_sf, u.is_online, 
                        u.profile_image, u.sign_image,
                        CONCAT_WS(' ', u.last_name, u.first_name, u.other_name) AS full_name,
                        (SELECT MAX(login_time) FROM user_activity WHERE user_id = u.id) AS last_activity
                    FROM users u
                    WHERE u.role NOT IN ({placeholders})
                    ORDER BY last_activity DESC, u.username ASC
                """
                cursor.execute(query, tuple(excluded_roles))
                users = cursor.fetchall()
    except Exception as e:
        print(f"Manage users error: {e}")
        flash("System error while retrieving user directory.", "danger")
        return redirect(url_for('home_blueprint.index'))
    
    return render_template('accounts/manage_users.html', users=users, num=len(users))

@login_required
@blueprint.route('/get_all_user_statuses', methods=['GET'])
def get_all_user_statuses():
    """Get online status for all users"""
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = """
                    SELECT u.id, u.is_online,
                           (SELECT MAX(timestamp) FROM activity_logs WHERE user_id = u.id) as last_seen
                    FROM users u
                """
                cursor.execute(query)
                results = cursor.fetchall()
                
                for row in results:
                    if row['last_seen']:
                        row['last_seen'] = row['last_seen'].strftime('%Y-%m-%d %H:%M')
                    else:
                        row['last_seen'] = "Never"
                
                return jsonify(results)
    except Exception as e:
        print(f"Error in bulk status check: {e}")
        return jsonify([]), 500

@login_required
@blueprint.route('/activity_logs/<int:id>', methods=['GET', 'POST'])
def activity_logs(id):
    """View user activity logs"""
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                query = """
                    SELECT ua.login_time, ua.logout_time, u.username, u.first_name, u.last_name
                    FROM user_activity ua
                    JOIN users u ON ua.user_id = u.id
                    WHERE ua.user_id = %s
                    ORDER BY ua.login_time DESC
                """
                cursor.execute(query, (id,))
                activities = cursor.fetchall()
                return render_template('accounts/activity_logs.html', activities=activities)
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'danger')
        return redirect(url_for('authentication_blueprint.login'))

@login_required
@blueprint.route('/add_user', methods=['GET', 'POST'])
@user_has_role(['super_admin', 'admin'])
def add_user():
    """Add new user"""
    if request.method == 'POST':
        # Collect form data
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        other_name = request.form.get('other_name')
        name_sf = request.form.get('name_sf')
        
        # Handle file uploads
        profile_image = request.files.get('profile_image')
        sign_image = request.files.get('sign_image')
        
        # Get crop data
        profile_crop = {
            'x': request.form.get('crop_x'),
            'y': request.form.get('crop_y'),
            'w': request.form.get('crop_w'),
            'h': request.form.get('crop_h')
        }
        
        sign_crop = {
            'x': request.form.get('sign_x'),
            'y': request.form.get('sign_y'),
            'w': request.form.get('sign_w'),
            'h': request.form.get('sign_h')
        }
        
        try:
            with get_db_connection() as connection:
                with connection.cursor() as cursor:
                    # Check existing username
                    cursor.execute('SELECT 1 FROM users WHERE username = %s', (username,))
                    if cursor.fetchone():
                        flash('Username already exists.', 'danger')
                        return render_template('accounts/add_user.html', role=session.get('role'))
                    
                    # Process images
                    profile_image_filename = handle_profile_image(profile_image, None, profile_crop) if profile_image else None
                    sign_image_filename = handle_sign_image(sign_image, None, sign_crop) if sign_image else None
                    
                    # Insert user
                    cursor.execute("""
                        INSERT INTO users 
                        (username, password, role, first_name, last_name, other_name, 
                         profile_image, name_sf, sign_image)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (username, password, role, first_name, last_name, other_name, 
                          profile_image_filename, name_sf, sign_image_filename))
                    
                    connection.commit()
                    flash('User added successfully!', 'success')
                    return redirect(url_for('home_blueprint.index'))
                    
        except Exception as err:
            flash(f'Error: {err}', 'danger')
            return render_template('accounts/add_user.html', role=session.get('role'))
    
    return render_template("accounts/add_user.html", role=session.get('role'))

@login_required
@blueprint.route('/edit_user/<int:id>', methods=['GET', 'POST'])
@user_has_role(['super_admin', 'admin'])
def edit_user(id):
    """Edit user information"""
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                user = get_user_by_id(id, connection)
                
                if not user:
                    flash("User not found.", "danger")
                    return redirect(url_for("home_blueprint.index"))
                
                if request.method == 'POST':
                    # Collect form data
                    username = request.form.get('username')
                    first_name = request.form.get('first_name')
                    last_name = request.form.get('last_name')
                    other_name = request.form.get('other_name')
                    name_sf = request.form.get('name_sf')
                    password = request.form.get('password')
                    role = request.form.get('role')
                    role1 = request.form.get('role1')
                    
                    # Normalize role1
                    if role1 in ('None', '', None):
                        role1 = None
                    
                    # Keep existing password if not provided
                    if not password:
                        password = user['password']
                    
                    # Handle image uploads
                    new_profile_file = request.files.get('profile_image')
                    new_sign_file = request.files.get('sign_image')
                    
                    # Get crop data
                    profile_crop = {
                        'x': request.form.get('crop_x'),
                        'y': request.form.get('crop_y'),
                        'w': request.form.get('crop_w'),
                        'h': request.form.get('crop_h')
                    } if new_profile_file else None
                    
                    sign_crop = {
                        'x': request.form.get('sign_x'),
                        'y': request.form.get('sign_y'),
                        'w': request.form.get('sign_w'),
                        'h': request.form.get('sign_h')
                    } if new_sign_file else None
                    
                    # Process images
                    profile_image_path = handle_profile_image(new_profile_file, id, profile_crop) if new_profile_file and new_profile_file.filename else user['profile_image']
                    sign_image_path = handle_sign_image(new_sign_file, id, sign_crop) if new_sign_file and new_sign_file.filename else user['sign_image']
                    
                    # Update database
                    cursor.execute("""
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s, other_name = %s,
                            name_sf = %s, password = %s, role = %s, role1 = %s,
                            profile_image = %s, sign_image = %s 
                        WHERE id = %s
                    """, (username, first_name, last_name, other_name, name_sf,
                          password, role, role1, profile_image_path, sign_image_path, id))
                    
                    connection.commit()
                    flash("User updated successfully!", "success")
                    
                    # Update session if current user
                    if session.get('id') == id:
                        session['first_name'] = first_name
                        session['last_name'] = last_name
                        session['role'] = role
                        session['profile_image'] = profile_image_path
                    
                    return redirect(url_for("authentication_blueprint.manage_users"))
                
                return render_template("accounts/edit_user.html", user=user)
                
    except Exception as e:
        flash(f"Error updating user: {str(e)}", "danger")
        return redirect(url_for("authentication_blueprint.edit_user", id=id))

@login_required
@blueprint.route('/view_user/<int:id>', methods=['GET'])
def view_user(id):
    """View user details"""
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            user = get_user_by_id(id, connection)
            
            if not user:
                flash("User not found.", "danger")
                return redirect(url_for("authentication_blueprint.manage_users"))
            
            # Get sub-categories
            cursor.execute("""
                SELECT sub.sub_category_id, sub.name AS sub_category_name, 
                       sub.description AS sub_category_description, cat.name AS category_name
                FROM sub_category sub
                JOIN category_list cat ON sub.category_id = cat.CategoryID
            """)
            all_sub_categories = cursor.fetchall()
            
            # Get user's assigned sub-categories
            cursor.execute('SELECT sub_category_id FROM other_roles WHERE user_id = %s', (id,))
            user_sub_category_ids = {row['sub_category_id'] for row in cursor.fetchall()}
    
    return render_template("accounts/view_user.html", user=user, 
                          all_sub_categories=all_sub_categories,
                          user_sub_category_ids=user_sub_category_ids)

@login_required
@blueprint.route('/edit_user_roles/<int:id>', methods=['GET', 'POST'])
@user_has_role(['super_admin', 'admin'])
def edit_user_roles(id):
    """Edit user sub-category roles"""
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            if request.method == 'POST':
                selected_sub_categories = request.form.getlist('sub_categories')
                
                # Clear existing roles
                cursor.execute('DELETE FROM other_roles WHERE user_id = %s', (id,))
                
                # Insert new roles
                for sub_category_id in selected_sub_categories:
                    cursor.execute("""
                        INSERT INTO other_roles (user_id, sub_category_id) 
                        VALUES (%s, %s)
                    """, (id, sub_category_id))
                
                connection.commit()
                flash('User roles updated successfully!', 'success')
                return redirect(url_for('authentication_blueprint.manage_users'))
            
            # GET request
            user = get_user_by_id(id, connection)
            cursor.execute('SELECT * FROM sub_category')
            all_sub_categories = cursor.fetchall()
            
            cursor.execute('SELECT sub_category_id FROM other_roles WHERE user_id = %s', (id,))
            user_sub_category_ids = {row['sub_category_id'] for row in cursor.fetchall()}
    
    return render_template("accounts/edit_user_roles.html", user=user,
                          all_sub_categories=all_sub_categories,
                          user_sub_category_ids=user_sub_category_ids)

@login_required
@blueprint.route('/view_user_cat_roles/<int:id>', methods=['GET'])
def view_user_cat_roles(id):
    """View user category roles"""
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            user = get_user_by_id(id, connection)
            
            cursor.execute('SELECT CategoryID, name, description FROM category_list')
            all_categories = cursor.fetchall()
            
            cursor.execute('SELECT category_id FROM category_roles WHERE user_id = %s', (id,))
            user_category_ids = {row['category_id'] for row in cursor.fetchall()}
    
    return render_template("accounts/view_user_cat_roles.html", user=user,
                          all_categories=all_categories,
                          user_category_ids=user_category_ids)

@login_required
@blueprint.route('/edit_user_cat_roles/<int:id>', methods=['GET', 'POST'])
@user_has_role(['super_admin', 'admin'])
def edit_user_cat_roles(id):
    """Edit user category roles"""
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            if request.method == 'POST':
                selected_categories = request.form.getlist('categories')
                
                # Clear existing roles
                cursor.execute('DELETE FROM category_roles WHERE user_id = %s', (id,))
                
                # Insert new roles
                for category_id in selected_categories:
                    cursor.execute("""
                        INSERT INTO category_roles (user_id, category_id) 
                        VALUES (%s, %s)
                    """, (id, category_id))
                
                connection.commit()
                flash('User category roles updated successfully!', 'success')
                return redirect(url_for('authentication_blueprint.manage_users'))
            
            # GET request
            user = get_user_by_id(id, connection)
            cursor.execute('SELECT * FROM category_list')
            all_categories = cursor.fetchall()
            
            cursor.execute('SELECT category_id FROM category_roles WHERE user_id = %s', (id,))
            user_category_ids = {row['category_id'] for row in cursor.fetchall()}
    
    return render_template("accounts/edit_user_cat_roles.html", user=user,
                          all_categories=all_categories,
                          user_category_ids=user_category_ids)

@login_required
@blueprint.route('/api/user/profile-image')
def profile_image():
    """Get current user's profile image"""
    if 'profile_image' in session:
        return jsonify({'profile_image': session['profile_image']})
    return jsonify({'error': 'Not logged in'}), 401

@login_required
@blueprint.route('/delete_user/<int:id>', methods=['GET'])
@user_has_role(['super_admin', 'admin'])
def delete_user(id):
    """Delete a user"""
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM users WHERE id = %s', (id,))
                connection.commit()
                flash('User deleted successfully!', 'success')
    except mysql.connector.Error as err:
        flash(f'Error: {err}', 'danger')
    
    return redirect(url_for('home_blueprint.index'))

@login_required
@blueprint.route('/edit_user_profile/<int:id>', methods=['GET', 'POST'])
def edit_user_profile(id):
    """Edit user's own profile (limited fields)"""
    # Ensure user can only edit their own profile
    if session.get('id') != id:
        flash('You can only edit your own profile.', 'danger')
        return redirect(url_for('home_blueprint.index'))
    
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                if request.method == 'POST':
                    username = request.form.get('username')
                    first_name = request.form.get('first_name')
                    last_name = request.form.get('last_name')
                    other_name = request.form.get('other_name')
                    password = request.form.get('password')
                    
                    current_user = get_user_by_id(id, connection)
                    if not current_user:
                        flash('User not found.', 'danger')
                        return redirect(url_for('home_blueprint.index'))
                    
                    # Keep existing password if not provided
                    final_password = password if password and password.strip() else current_user['password']
                    
                    # Handle images
                    profile_file = request.files.get('profile_image')
                    sign_file = request.files.get('sign_image')
                    
                    profile_crop = {
                        'x': request.form.get('crop_x'),
                        'y': request.form.get('crop_y'),
                        'w': request.form.get('crop_w'),
                        'h': request.form.get('crop_h')
                    } if profile_file else None
                    
                    sign_crop = {
                        'x': request.form.get('sign_x'),
                        'y': request.form.get('sign_y'),
                        'w': request.form.get('sign_w'),
                        'h': request.form.get('sign_h')
                    } if sign_file else None
                    
                    profile_path = handle_profile_image(profile_file, id, profile_crop) if profile_file and profile_file.filename else current_user['profile_image']
                    sign_path = handle_sign_image(sign_file, id, sign_crop) if sign_file and sign_file.filename else current_user['sign_image']
                    
                    # Update user (role and role1 are not changed here for security)
                    cursor.execute("""
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s, 
                            other_name = %s, password = %s, profile_image = %s, sign_image = %s
                        WHERE id = %s
                    """, (username, first_name, last_name, other_name,
                          final_password, profile_path, sign_path, id))
                    
                    connection.commit()
                    
                    # Update session
                    session['username'] = username
                    session['first_name'] = first_name
                    session['last_name'] = last_name
                    session['profile_image'] = profile_path
                    
                    flash('Profile updated successfully!', 'success')
                    return redirect(url_for('home_blueprint.index'))
                
                # GET request
                user = get_user_by_id(id, connection)
                if not user:
                    flash('User not found!', 'danger')
                    return redirect(url_for('home_blueprint.index'))
                
                return render_template('accounts/edit_user_profile.html', user=user)
                
    except Exception as e:
        print(f"Error updating profile: {e}")
        flash("An unexpected error occurred. Please try again.", "danger")
        return redirect(url_for('home_blueprint.index'))

# ============================================
# ERROR HANDLERS
# ============================================

@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403

@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404

@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500






@blueprint.route('/check_username', methods=['POST'])
@login_required
def check_username():
    username = request.form.get('username')

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE username = %s",
                    (username,)
                )
                user = cursor.fetchone()

                if user:
                    return jsonify({"exists": True})
                else:
                    return jsonify({"exists": False})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
