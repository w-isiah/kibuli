from flask import (
    render_template, redirect, request, url_for, flash, session, current_app, jsonify
)
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from PIL import Image
import os
import mysql.connector
from flask import request, render_template, redirect, url_for, flash


from apps import get_db_connection
from apps.authentication import blueprint
from apps.utils.decorators import login_required  # Adjust path as needed
        
from werkzeug.utils import secure_filename
import os
from flask import current_app

from datetime import datetime
import pytz



def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)



def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']



@blueprint.route('/', methods=['GET', 'POST'])
def route_default():
    return redirect(url_for('authentication_blueprint.login'))





import uuid
from flask import request, render_template, flash, session, redirect, url_for

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            with get_db_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                    user = cursor.fetchone()

                    if not user:
                        flash('Username not found.', 'danger')
                        return render_template('accounts/login.html')

                    # ⚠️ Use password hashing in production!
                    if user['password'] != password:
                        flash('Incorrect password.', 'danger')
                        return render_template('accounts/login.html')

                    # Record login time
                    login_time = get_kampala_time()
                    cursor.execute(
                        "INSERT INTO user_activity (user_id, login_time) VALUES (%s, %s)",
                        (user['id'], login_time)
                    )
                    cursor.execute(
                        "UPDATE users SET is_online = 1 WHERE id = %s",
                        (user['id'],)
                    )

                    # Generate and store session token
                    session_token = str(uuid.uuid4())
                    session['token'] = session_token
                    cursor.execute(
                        "UPDATE users SET session_token = %s WHERE id = %s",
                        (session_token, user['id'])
                    )

                    # Commit changes
                    conn.commit()

                    # Set session values
                    # We add 'assigned_db' using the 'name_sf' field from your database
                    session.update({
                        'loggedin': True,
                        'id': user['id'],
                        'username': user['username'],
                        'assigned_db': user.get('assigned_db'), # Fallback to default if empty
                        'profile_image': user.get('profile_image'),
                        'first_name': user.get('first_name'),
                        'role': user.get('role'),
                        'role1': user.get('role1'),
                        'last_activity': login_time
                    })

                    session.permanent = False  # Session ends with browser close

                    flash(f"Login successful! Connected to {session['assigned_db']}", 'success')
                    return redirect(url_for('home_blueprint.index'))

        except Exception as e:
            flash(f"An error occurred: {str(e)}", 'danger')

    return render_template('accounts/login.html')







@blueprint.before_app_request
def check_token_validity():
    if 'loggedin' in session:
        user_id = session.get('id')
        token = session.get('token')

        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT session_token FROM users WHERE id = %s", (user_id,))
                result = cursor.fetchone()

                if result and token != result['session_token']:
                    session.clear()
                    flash('You were logged out by an administrator.', 'info')
                    return redirect(url_for('authentication_blueprint.login'))



import uuid

@login_required
@blueprint.route('/force_logout/<int:user_id>')
def force_logout(user_id):
    role = session.get('role')
    if role not in ['admin', 'super_admin']:
        flash("You do not have permission to force logout users.", "warning")
        return redirect(url_for('authentication_blueprint.login'))

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                current_time = get_kampala_time().replace(tzinfo=None)

                # Update user activity and is_online
                cursor.execute("""
                    UPDATE user_activity
                    SET logout_time = %s
                    WHERE user_id = %s AND logout_time IS NULL
                    ORDER BY login_time DESC
                    LIMIT 1
                """, (current_time, user_id))

                cursor.execute("UPDATE users SET is_online = 0 WHERE id = %s", (user_id,))

                # Invalidate session by changing token
                new_token = str(uuid.uuid4())
                cursor.execute("UPDATE users SET session_token = %s WHERE id = %s", (new_token, user_id))

                connection.commit()

        flash("User has been signed out successfully.", "success")
    except Exception as e:
        flash(f"Error during forced logout: {str(e)}", "danger")

    return redirect(url_for('authentication_blueprint.manage_users'))









@login_required
@blueprint.before_app_request
def check_inactivity():
    """Check for session timeout due to inactivity."""
    if 'loggedin' in session:
        last_activity_str = session.get('last_activity')
        if last_activity_str:
            try:
                # Parse ISO 8601 string with timezone info
                last_activity = datetime.fromisoformat(last_activity_str)
            except Exception:
                last_activity = None

            current_time = get_kampala_time()

            if last_activity:
                time_diff = current_time - last_activity
                # Timeout after 30 minutes of inactivity
                if time_diff > timedelta(minutes=30):
                    try:
                        with get_db_connection() as connection:
                            with connection.cursor(dictionary=True) as cursor:
                                # Strip tzinfo before storing in MariaDB DATETIME
                                logout_time_naive = current_time.replace(tzinfo=None)

                                cursor.execute("""
                                    UPDATE user_activity 
                                    SET logout_time = %s 
                                    WHERE user_id = %s AND logout_time IS NULL
                                """, (logout_time_naive, session['id']))

                                cursor.execute("UPDATE users SET is_online = 0 WHERE id = %s", (session['id'],))
                                connection.commit()

                        session.clear()
                        flash('Session expired due to inactivity.', 'warning')
                        return redirect(url_for('authentication_blueprint.login'))
                    except Exception as e:
                        flash(f"An error occurred while updating the logout status: {str(e)}", 'danger')
                        session.clear()
                        return redirect(url_for('authentication_blueprint.login'))

        # Update last_activity timestamp on each request as ISO string with timezone
        session['last_activity'] = get_kampala_time().isoformat()











@blueprint.route('/logout')
def logout():
    user_id = session.get('id')
    username = session.get('username')

    print(f"Logout called for user_id: {user_id}, username: {username}")

    if user_id and username:
        try:
            with get_db_connection() as connection:
                with connection.cursor(dictionary=True) as cursor:
                    current_time = get_kampala_time()
                    current_time_naive = current_time.replace(tzinfo=None)

                    print(f"Updating user_activity logout_time for user_id={user_id} to {current_time_naive}")
                    cursor.execute("""
                        UPDATE user_activity 
                        SET logout_time = %s 
                        WHERE user_id = %s AND logout_time IS NULL
                    """, (current_time_naive, user_id))

                    print(f"Setting is_online = 0 for user_id={user_id}")
                    cursor.execute("UPDATE users SET is_online = 0 WHERE id = %s", (user_id,))

                    connection.commit()
                    print(f"User '{username}' logged out successfully.")



                    

        except Exception as e:
            print(f"Exception in logout route: {e}")
            flash(f"An error occurred while updating the logout status: {str(e)}", 'danger')

    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('authentication_blueprint.login'))













@blueprint.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Collect form data
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone_number = request.form.get('phone_number', '').strip()

        # Default role
        role = 'applicant'

        # Basic validation (check if essential fields are filled)
        if not username or not password or not first_name or not last_name or not email:
            flash('Please fill in all required fields.', 'danger')
            return render_template('accounts/signup.html')

        try:
            # Database connection
            with get_db_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:

                    # Check if the username already exists in the database
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    if cursor.fetchone():
                        flash('Username already exists.', 'danger')
                        return render_template('accounts/signup.html')

                    # Check if the email already exists in the database
                    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cursor.fetchone():
                        flash('Email address is already in use.', 'danger')
                        return render_template('accounts/signup.html')

                    # Insert the new user into the database (password is not hashed here)
                    cursor.execute(
                        """
                        INSERT INTO users (
                            username, password, role,
                            first_name, last_name,
                            email, phone_number,
                            is_online
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                        """,
                        (
                            username,
                            password,  # No password hashing
                            role,
                            first_name,
                            last_name,
                            email,
                            phone_number
                        )
                    )

                    # Commit the transaction
                    conn.commit()

                    # Success message and redirect to login page
                    flash('Account created successfully. Please sign in.', 'success')
                    return redirect(url_for('authentication_blueprint.login'))

        except Exception as e:
            # In case of error, flash an error message
            flash('An error occurred during registration.', 'danger')
            print(e)

    # GET request: show the signup form
    return render_template('accounts/signup.html')











@login_required
@blueprint.route('/manage_users')
def manage_users():
    role = session.get('role')

    excluded_roles_map = {
        'admin': ['admin', 'super_admin'],
        'inventory_manager': ['admin', 'inventory_manager', 'super_admin', 'class_teacher'],
        'super_admin': ['super_admin']
    }

    if role not in excluded_roles_map:
        flash('You do not have permission to access this page.', 'warning')
        return redirect(url_for('authentication_blueprint.login'))

    excluded_roles = excluded_roles_map[role]

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                placeholders = ','.join(['%s'] * len(excluded_roles))
                query = f"""
                    SELECT
                        id,
                        username,
                        role,
                        name_sf,
                        is_online,
                        CONCAT_WS(' ', last_name, first_name, other_name) AS full_name,
                        profile_image,
                        sign_image
                    FROM users
                    WHERE role NOT IN ({placeholders})
                    ORDER BY username ASC
                """
                cursor.execute(query, tuple(excluded_roles))
                users = cursor.fetchall()

    except Exception:
        flash("Error fetching user data.", "danger")
        return redirect(url_for('home_blueprint.index'))

    return render_template('accounts/manage_users.html', users=users, num=len(users))













@login_required
# Flask route (suggested)
@blueprint.route('/get_all_user_statuses', methods=['GET'])
def get_all_user_statuses():
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT id, is_online FROM users")
                statuses = cursor.fetchall()
                return jsonify(statuses)
    except Exception as e:
        return jsonify([]), 500





@login_required
@blueprint.route('/activity_logs/<int:id>', methods=['GET', 'POST'])
def activity_logs(id):
    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                # SQL JOIN query to combine user_activity and users tables
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







@blueprint.route('/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form['username']
        password = request.form['password']  # Storing raw password
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        other_name = request.form.get('other_name', None)
        name_sf = request.form.get('name_sf', None)

        # Handle profile image upload (if present)
        profile_image = None
        if 'profile_image' in request.files:
            profile_image = request.files['profile_image']

        # Handle signature image upload (if present)
        sign_image = None
        if 'sign_image' in request.files:
            sign_image = request.files['sign_image']

        # Check if the username already exists in the database
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1 FROM users WHERE username = %s', (username,))
                if cursor.fetchone():
                    flash('Username already exists. Please choose a different one.', 'danger')
                    return render_template('accounts/add_user.html', role=session.get('role'), username=session.get('username'))

                try:
                    # Handle the profile image and signature image, saving or fetching from DB if necessary
                    profile_image_filename = handle_profile_image(cursor, profile_image, None)
                    sign_image_filename = handle_sign_image(cursor, sign_image, None)

                    # Insert the new user data into the database (storing raw password)
                    cursor.execute(''' 
                        INSERT INTO users 
                        (username, password, role, first_name, last_name, other_name, profile_image, name_sf, sign_image)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (username, password, role, first_name, last_name, other_name, profile_image_filename, name_sf, sign_image_filename))

                    connection.commit()
                    flash('User added successfully!', 'success')
                except Exception as err:
                    flash(f'Error: {err}', 'danger')
                    return render_template('accounts/add_user.html', role=session.get('role'), username=session.get('username'))

        return redirect(url_for('home_blueprint.index'))

    return render_template("accounts/add_user.html", role=session.get('role'), username=session.get('username'))









@blueprint.route('/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:

            # Fetch user for both GET and default values on POST
            cursor.execute("SELECT * FROM users WHERE id = %s", (id,))
            user = cursor.fetchone()

            if not user:
                flash("User not found.", "danger")
                return redirect(url_for("home_blueprint.index"))

            if request.method == 'POST':
                try:
                    # Get form inputs
                    username = request.form.get('username')
                    first_name = request.form.get('first_name')
                    last_name = request.form.get('last_name')
                    other_name = request.form.get('other_name')
                    name_sf = request.form.get('name_sf')  # New field added
                    password = request.form.get('password')
                    role = request.form.get('role')
                    role1 = request.form.get('role1') or None
                    profile_image = request.files.get('profile_image')
                    sign_image = request.files.get('sign_image')

                    # Normalize role1
                    if role1 in ('None', ''):
                        role1 = None

                    # Use existing password if blank
                    if not password:
                        password = get_user_password(cursor, id)

                    # Handle image upload (or keep existing)
                    profile_image_path = handle_profile_image(cursor, profile_image, id)
                    sign_image_path = handle_sign_image(cursor, sign_image, id)

                    # Update user in DB including name_sf
                    cursor.execute(''' 
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s, other_name = %s,
                            name_sf = %s, password = %s, role = %s, role1 = %s,
                            profile_image = %s, sign_image = %s 
                        WHERE id = %s
                    ''', (
                        username, first_name, last_name, other_name, name_sf,
                        password, role, role1, profile_image_path, sign_image_path, id
                    ))
                    connection.commit()

                    flash("User updated successfully!", "success")
                    return redirect(url_for("authentication_blueprint.manage_users"))

                except Exception as e:
                    flash(f"Error updating user: {str(e)}", "danger")
                    return redirect(url_for("authentication_blueprint.edit_user", id=id))

            # GET request – render edit form
            return render_template("accounts/edit_user.html", user=user)







def handle_sign_image(cursor, sign_image, user_id):
    # Check if a signature image is provided and is a valid file type
    if sign_image and allowed_file(sign_image.filename):
        filename = secure_filename(sign_image.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Save the signature image to the specified upload folder
        sign_image.save(file_path)
        
        # Return the filename to save in the database
        return filename
    else:
        # If no new signature image, fetch the existing one from the DB
        cursor.execute('SELECT sign_image FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        
        # Return the existing signature image filename or None if not found
        return result['sign_image'] if result else None








def handle_profile_image(cursor, profile_image, user_id):
    # Check if a profile image is provided and it's a valid file type
    if profile_image and allowed_file(profile_image.filename):
        filename = secure_filename(profile_image.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Save the image to the specified upload folder
        profile_image.save(file_path)
        
        # Return the filename to save in the database
        return filename
    else:
        # If no new image, fetch the existing profile image from the DB
        cursor.execute('SELECT profile_image FROM users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        
        # Return the existing profile image filename or None if not found
        return result['profile_image'] if result else None
















@login_required
@blueprint.route('/view_user/<int:id>', methods=['GET'])
def view_user(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            # Retrieve the user information based on the user ID
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Join sub_category and category_list to fetch the category name along with sub-category details
            cursor.execute('''
                SELECT sub.sub_category_id, sub.name AS sub_category_name, sub.description AS sub_category_description, 
                       cat.name AS category_name
                FROM sub_category sub
                JOIN category_list cat ON sub.category_id = cat.CategoryID
            ''')
            all_sub_categories = cursor.fetchall()

            # Fetch the sub_category_ids associated with the user from the other_roles table
            cursor.execute('SELECT sub_category_id FROM other_roles WHERE user_id = %s', (id,))
            user_sub_category_ids = {row['sub_category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/view_user.html",
        user=user,
        all_sub_categories=all_sub_categories,
        user_sub_category_ids=user_sub_category_ids
    )









@login_required
@blueprint.route('/edit_user_roles/<int:id>', methods=['GET', 'POST'])
def edit_user_roles(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            if request.method == 'POST':
                # Retrieve the list of selected sub_category_ids from the form
                selected_sub_categories = request.form.getlist('sub_categories')

                # Clear the previous roles for the user in the other_roles table
                cursor.execute('DELETE FROM other_roles WHERE user_id = %s', (id,))
                connection.commit()

                # Add the newly selected roles to the other_roles table
                for sub_category_id in selected_sub_categories:
                    cursor.execute('''
                        INSERT INTO other_roles (user_id, sub_category_id) 
                        VALUES (%s, %s)
                    ''', (id, sub_category_id))
                connection.commit()

                flash('User roles updated successfully!', 'success')
                return redirect(url_for('authentication_blueprint.manage_users'))

            # Retrieve the user information to pre-fill the form
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Get all sub-categories to display
            cursor.execute('SELECT * FROM sub_category')
            all_sub_categories = cursor.fetchall()

            # Get the current sub-categories assigned to the user
            cursor.execute('SELECT sub_category_id FROM other_roles WHERE user_id = %s', (id,))
            user_sub_category_ids = {row['sub_category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/edit_user_roles.html", 
        user=user, 
        all_sub_categories=all_sub_categories, 
        user_sub_category_ids=user_sub_category_ids
    )









@login_required
@blueprint.route('/view_user_cat_roles/<int:id>', methods=['GET'])
def view_user_cat_roles(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            # Retrieve the user information based on the user ID
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Fetch all categories
            cursor.execute('SELECT CategoryID, name, description FROM category_list')
            all_categories = cursor.fetchall()

            # Fetch the category_ids associated with the user from the category_roles table
            cursor.execute('SELECT category_id FROM category_roles WHERE user_id = %s', (id,))
            user_category_ids = {row['category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/view_user_cat_roles.html",
        user=user,
        all_categories=all_categories,
        user_category_ids=user_category_ids
    )









@login_required
@blueprint.route('/edit_user_cat_roles/<int:id>', methods=['GET', 'POST'])
def edit_user_cat_roles(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            if request.method == 'POST':
                # Retrieve the list of selected category_ids from the form
                selected_categories = request.form.getlist('categories')

                # Clear previous category roles for the user
                cursor.execute('DELETE FROM category_roles WHERE user_id = %s', (id,))
                connection.commit()

                # Insert the newly selected categories
                for category_id in selected_categories:
                    cursor.execute('''
                        INSERT INTO category_roles (user_id, category_id) 
                        VALUES (%s, %s)
                    ''', (id, category_id))
                connection.commit()

                flash('User category roles updated successfully!', 'success')
                return redirect(url_for('authentication_blueprint.manage_users'))

            # Retrieve user info
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # Get all categories
            cursor.execute('SELECT * FROM category_list')
            all_categories = cursor.fetchall()

            # Get current categories assigned to the user
            cursor.execute('SELECT category_id FROM category_roles WHERE user_id = %s', (id,))
            user_category_ids = {row['category_id'] for row in cursor.fetchall()}

    return render_template(
        "accounts/edit_user_cat_roles.html", 
        user=user, 
        all_categories=all_categories, 
        user_category_ids=user_category_ids
    )

















@login_required
def get_user_password(cursor, user_id):
    cursor.execute('SELECT password FROM users WHERE id = %s', (user_id,))
    return cursor.fetchone()['password']






@login_required
@blueprint.route('/api/user/profile-image')
def profile_image():
    if 'profile_image' in session:
        return jsonify({
            'profile_image': session['profile_image']
        })
    else:
        return jsonify({'error': 'Not logged in'}), 401



@login_required
# Route for deleting a user
@blueprint.route('/delete_user/<int:id>', methods=['GET'])
def delete_user(id):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            try:
                cursor.execute('DELETE FROM users WHERE id = %s', (id,))
                connection.commit()
                flash('User deleted successfully!', 'success')
            except mysql.connector.Error as err:
                flash(f'Error: {err}', 'danger')

    return redirect(url_for('home_blueprint.index'))



@login_required
def handle_image_upload(image_file):
    filename = secure_filename(image_file.filename)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    profile_image_path = os.path.join(upload_folder, filename)

    try:
        img = Image.open(image_file)
        max_width, max_height = 500, 500
        width, height = img.size
        if width > max_width or height > max_height:
            img.thumbnail((max_width, max_height))
            img.save(profile_image_path, optimize=True, quality=85)
        else:
            img.save(profile_image_path)
    except Exception as e:
        flash(f"Error processing image: {e}", 'danger')
        return None

    # Return filename or relative path as per your app needs
    return filename





@login_required
@blueprint.route('/edit_user_profile/<int:id>', methods=['GET', 'POST'])
def edit_user_profile(id):
    with get_db_connection() as connection:
        with connection.cursor(dictionary=True) as cursor:
            
            # POST request - Handle profile update
            if request.method == 'POST':
                # Collect form data
                username = request.form['username']
                first_name = request.form['first_name']
                last_name = request.form['last_name']
                other_name = request.form['other_name']
                password = request.form['password']
                profile_image = request.files.get('profile_image')

                # Use existing password if none is provided
                password = password if password else get_user_password(cursor, id)
                
                # Process profile image
                profile_image_path = handle_profile_image(cursor, profile_image, id)

                try:
                    # Update user details in the database
                    cursor.execute(''' 
                        UPDATE users 
                        SET username = %s, first_name = %s, last_name = %s, other_name = %s, password = %s, profile_image = %s
                        WHERE id = %s
                    ''', (username, first_name, last_name, other_name, password, profile_image_path, id))
                    connection.commit()
                    flash('User updated successfully!', 'success')
                except mysql.connector.Error as err:
                    flash(f'Error: {err}', 'danger')

                # Redirect after successful update
                return redirect(url_for('home_blueprint.index'))

            # GET request - Fetch user data to populate the edit form
            cursor.execute('SELECT * FROM users WHERE id = %s', (id,))
            user = cursor.fetchone()

            # If user not found, show error and redirect
            if not user:
                flash('User not found!', 'danger')
                return redirect(url_for('home_blueprint.index'))

    return render_template('accounts/edit_user_profile.html', user=user)










# Error Handlers
@login_required
@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403
@login_required
@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404
@login_required
@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
