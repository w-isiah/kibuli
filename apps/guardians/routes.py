from apps.guardians import blueprint
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

import base64



# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@blueprint.route('/guardians')
def guardians():
    """Fetches all guardians and renders the manage guardians page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all guardians from the database
    cursor.execute('SELECT * FROM guardians ORDER BY last_name')
    guardians = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('guardians/guardians.html', guardians=guardians,segment='guardians')






@blueprint.route('/add_guardian', methods=['GET', 'POST'])
def add_guardian():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get all pupils to populate dropdown
    cursor.execute("SELECT * FROM pupils ORDER BY last_name")
    pupils = cursor.fetchall()

    if request.method == 'POST':
        # Retrieve form data
        pupil_id = request.form.get('pupil_id')
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')
        relationship = request.form.get('relationship')
        contact_number = request.form.get('contact_number')

        # Initialize filenames for images
        image_filename = None
        sign_image_filename = None

        # Handle profile image upload
        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'],image_filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image_file.save(image_path)

        # Handle signature image upload
        sign_image_file = request.files.get('sign_image')
        if sign_image_file and allowed_file(sign_image_file.filename):
            sign_image_filename = secure_filename(sign_image_file.filename)
            sign_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'],sign_image_filename)
            os.makedirs(os.path.dirname(sign_image_path), exist_ok=True)
            sign_image_file.save(sign_image_path)

        # Insert guardian data into the DB with file paths
        cursor.execute(
            '''
            INSERT INTO guardians 
                (pupil_id, first_name, other_name, last_name, relationship, contact_number, image, sign_image)
            VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (pupil_id, first_name, other_name, last_name, relationship, contact_number, image_filename, sign_image_filename)
        )

        connection.commit()
        flash("Guardian successfully added!", "success")
        return redirect(url_for('guardians_blueprint.add_guardian'))

    cursor.close()
    connection.close()

    return render_template('guardians/add_guardian.html', segment='add_guardian', pupils=pupils)












@blueprint.route('/edit_guardian/<int:guardian_id>', methods=['GET', 'POST'])
def edit_guardian(guardian_id):
    # Connect to the database
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the guardian data from the database
    cursor.execute('SELECT * FROM guardians WHERE guardian_id = %s', (guardian_id,))
    guardian = cursor.fetchone()

    if not guardian:
        flash("Guardian not found!")
        return redirect(url_for('guardians_blueprint.guardians'))  # Redirect to guardians list page or home

    if request.method == 'POST':
        # Get the form data
        pupil_id = request.form.get('pupil_id')
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')

        # Default to the existing image if no new one is uploaded
        image_filename = guardian['image']
        sign_image_filename = guardian['sign_image']
        
        image_file = request.files.get('image')
        sign_image_file = request.files.get('sign_image')

        # Handle the image file upload
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{guardian_id}_{filename}"  # Rename with guardian ID to avoid conflicts
            image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'images')  # Set the folder for images
            os.makedirs(image_folder, exist_ok=True)  # Ensure the folder exists
            image_path = os.path.join(image_folder, image_filename)
            image_file.save(image_path)

        # Handle the signature image file upload
        if sign_image_file and allowed_file(sign_image_file.filename):
            sign_filename = secure_filename(sign_image_file.filename)
            sign_image_filename = f"{guardian_id}_{sign_filename}"  # Rename with guardian ID to avoid conflicts
            sign_image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'signatures')  # Set the folder for signatures
            os.makedirs(sign_image_folder, exist_ok=True)  # Ensure the folder exists
            sign_image_path = os.path.join(sign_image_folder, sign_image_filename)
            sign_image_file.save(sign_image_path)

        # Update the guardian data in the database with the new or existing image paths
        cursor.execute(''' 
            UPDATE guardians
            SET pupil_id = %s, first_name = %s, other_name = %s, last_name = %s, 
                image = %s, sign_image = %s
            WHERE guardian_id = %s
        ''', (pupil_id, first_name, other_name, last_name, image_filename, sign_image_filename, guardian_id))

        # Commit the transaction
        connection.commit()

        flash("Guardian updated successfully!", "success")
        return redirect(url_for('guardians_blueprint.guardians'))  # Redirect to guardian list or home

    cursor.close()
    connection.close()

    return render_template('guardians/edit_guardian.html', guardian=guardian)













@blueprint.route('/delete_guardian/<int:guardians_id>')
def delete_guardian(guardians_id):
    """Deletes a guardians from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the guardians with the specified ID
        cursor.execute('DELETE FROM guardians WHERE guardian_id = %s', (guardians_id,))
        connection.commit()
        flash("guardians deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('guardians_blueprint.guardians'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("guardians/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'guardians'

        return segment

    except:
        return None
