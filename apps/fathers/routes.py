from apps.fathers import blueprint
from flask import render_template, request, redirect, url_for, flash, current_app
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
import re  # <-- Add this line
from apps import get_db_connection
from jinja2 import TemplateNotFound


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@blueprint.route('/fathers')
def fathers():
    """Fetches all fathers and renders the manage fathers page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all fathers from the database
    cursor.execute('SELECT * FROM fathers ORDER BY last_name')
    fathers = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('fathers/fathers.html', fathers=fathers,segment='fathers')




# Route to add a new father
@blueprint.route('/add_father', methods=['GET', 'POST'])
def add_father():
    # Establish DB connection and fetch pupils data
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM pupils ORDER BY last_name ")
    pupils = cursor.fetchall()  # Get all pupils

    if request.method == 'POST':
        # Retrieve form data
        pupil_id = request.form.get('pupil_id')
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')

        # Initialize filenames for images
        image_filename = None
        sign_image_filename = None

        # Handle profile image upload
        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image_file.save(image_path)

        # Handle signature image upload
        sign_image_file = request.files.get('sign_image')
        if sign_image_file and allowed_file(sign_image_file.filename):
            sign_image_filename = secure_filename(sign_image_file.filename)
            sign_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], sign_image_filename)
            os.makedirs(os.path.dirname(sign_image_path), exist_ok=True)
            sign_image_file.save(sign_image_path)

        # Insert the father data into the database
        cursor.execute(
            '''INSERT INTO fathers (pupil_id, first_name, other_name, last_name, image, sign_image)
               VALUES (%s, %s, %s, %s, %s, %s)''',
            (pupil_id, first_name, other_name, last_name, image_filename, sign_image_filename)
        )

        # Commit changes and flash success message
        connection.commit()
        flash("Father successfully added!", "success")

        # Redirect to the 'add_father' page after successful form submission
        return redirect(url_for('fathers_blueprint.add_father'))

    # Close cursor and connection
    cursor.close()
    connection.close()

    # Render the 'add_father.html' template with the pupils list
    return render_template('fathers/add_father.html', segment='add_father', pupils=pupils)

















@blueprint.route('/edit_father/<int:father_id>', methods=['GET', 'POST'])
def edit_father(father_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the father record
    cursor.execute('SELECT * FROM fathers WHERE father_id = %s', (father_id,))
    father = cursor.fetchone()

    if not father:
        flash("Father not found!", "danger")
        return redirect(url_for('fathers_blueprint.fathers'))

    # Fetch pupils for dropdown
    cursor.execute('SELECT * FROM pupils ORDER BY first_name')
    pupils = cursor.fetchall()

    if request.method == 'POST':
        # Get form fields
        pupil_id = request.form.get('pupil_id')
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')

        # Retain existing images by default
        image_filename = father['image']
        sign_image_filename = father['sign_image']

        # Define upload folder early
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
        os.makedirs(upload_folder, exist_ok=True)

        # Process new image upload if present
        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{father_id}_img_{filename}"
            image_path = os.path.join(upload_folder, image_filename)
            image_file.save(image_path)

        # Process new sign image upload if present
        sign_image_file = request.files.get('sign_image')
        if sign_image_file and allowed_file(sign_image_file.filename):
            sign_filename = secure_filename(sign_image_file.filename)
            sign_image_filename = f"{father_id}_sign_{sign_filename}"
            sign_image_path = os.path.join(upload_folder, sign_image_filename)
            sign_image_file.save(sign_image_path)

        # Update the father's data in DB
        cursor.execute('''
            UPDATE fathers
            SET pupil_id = %s, first_name = %s, other_name = %s, last_name = %s,
                image = %s, sign_image = %s
            WHERE father_id = %s
        ''', (pupil_id, first_name, other_name, last_name,
              image_filename, sign_image_filename, father_id))

        connection.commit()
        flash("Father updated successfully!", "success")
        return redirect(url_for('fathers_blueprint.fathers'))

    cursor.close()
    connection.close()

    return render_template('fathers/edit_father.html', father=father, pupils=pupils)

















@blueprint.route('/delete_father/<int:fathers_id>')
def delete_father(fathers_id):
    """Deletes a fathers from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the fathers with the specified ID
        cursor.execute('DELETE FROM fathers WHERE father_id = %s', (fathers_id,))
        connection.commit()
        flash("fathers deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('fathers_blueprint.fathers'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("fathers/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'fathers'

        return segment

    except:
        return None
