from apps.mothers import blueprint
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


@blueprint.route('/mothers')
def mothers():
    """Fetches all mothers and renders the manage mothers page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all mothers from the database
    cursor.execute('SELECT * FROM mothers ORDER BY last_name')
    mothers = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('mothers/mothers.html', mothers=mothers,segment='mothers')




# Route to add a new mother
@blueprint.route('/add_mother', methods=['GET', 'POST'])
def add_mother():
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

        # Insert the mother data into the database
        cursor.execute(
            '''INSERT INTO mothers (pupil_id, first_name, other_name, last_name, image, sign_image)
               VALUES (%s, %s, %s, %s, %s, %s)''',
            (pupil_id, first_name, other_name, last_name, image_filename, sign_image_filename)
        )

        # Commit changes and flash success message
        connection.commit()
        flash("mother successfully added!", "success")

        # Redirect to the 'add_mother' page after successful form submission
        return redirect(url_for('mothers_blueprint.add_mother'))

    # Close cursor and connection
    cursor.close()
    connection.close()

    # Render the 'add_mother.html' template with the pupils list
    return render_template('mothers/add_mother.html', segment='add_mother', pupils=pupils)










@blueprint.route('/edit_mother/<int:mother_id>', methods=['GET', 'POST'])
def edit_mother(mother_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Fetch the mother
        cursor.execute('SELECT * FROM mothers WHERE mother_id = %s', (mother_id,))
        mother = cursor.fetchone()

        if not mother:
            flash("Mother not found!", "danger")
            return redirect(url_for('mothers_blueprint.mothers'))

        # Fetch all pupils
        cursor.execute('SELECT * FROM pupils ORDER BY first_name')
        pupils = cursor.fetchall()

        if request.method == 'POST':
            # Form data
            pupil_id = request.form.get('pupil_id')
            first_name = request.form.get('first_name').strip()
            other_name = request.form.get('other_name').strip()
            last_name = request.form.get('last_name').strip()

            # Upload folder
            upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
            os.makedirs(upload_folder, exist_ok=True)

            # Image fields default to existing values
            image_filename = mother['image']
            sign_image_filename = mother['sign_image']

            # Handle image upload
            image_file = request.files.get('image')
            if image_file and allowed_file(image_file.filename):
                image_name = secure_filename(image_file.filename)
                image_filename = f"{mother_id}_{image_name}"
                image_path = os.path.join(upload_folder, image_filename)
                image_file.save(image_path)

            # Handle sign image upload
            sign_image_file = request.files.get('sign_image')
            if sign_image_file and allowed_file(sign_image_file.filename):
                sign_name = secure_filename(sign_image_file.filename)
                sign_image_filename = f"{mother_id}_{sign_name}"
                sign_image_path = os.path.join(upload_folder, sign_image_filename)
                sign_image_file.save(sign_image_path)

            # Update DB
            cursor.execute('''
                UPDATE mothers
                SET pupil_id = %s, first_name = %s, other_name = %s, last_name = %s,
                    image = %s, sign_image = %s
                WHERE mother_id = %s
            ''', (pupil_id, first_name, other_name, last_name,
                  image_filename, sign_image_filename, mother_id))

            connection.commit()
            flash("Mother updated successfully!", "success")
            return redirect(url_for('mothers_blueprint.mothers'))

        return render_template('mothers/edit_mother.html', mother=mother, pupils=pupils)

    finally:
        cursor.close()
        connection.close()














@blueprint.route('/delete_mother/<int:mothers_id>')
def delete_mother(mothers_id):
    """Deletes a mothers from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the mothers with the specified ID
        cursor.execute('DELETE FROM mothers WHERE mother_id = %s', (mothers_id,))
        connection.commit()
        flash("mothers deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('mothers_blueprint.mothers'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("mothers/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'mothers'

        return segment

    except:
        return None
