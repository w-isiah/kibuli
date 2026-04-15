from apps.subjects import blueprint
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


@blueprint.route('/subjects')
def subjects():
    """Fetches all subjects and renders the manage subjects page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all subjects from the database
    cursor.execute('SELECT * FROM subjects ORDER BY subject_name')
    subjects = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('subjects/subjects.html', subjects=subjects,segment='subjects')




# Route to add a new subject
@blueprint.route('/add_subject', methods=['GET', 'POST'])
def add_subject():
    # Establish DB connection
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        # Retrieve form data for subject details
        subject_code = request.form.get('subject_code')
        subject_name = request.form.get('subject_name')
        description = request.form.get('description')
        grade_level = request.form.get('grade_level')

        # Insert the subject data into the database
        cursor.execute(
            '''INSERT INTO subjects (subject_code, subject_name, description, grade_level)
               VALUES (%s, %s, %s, %s)''',
            (subject_code, subject_name, description, grade_level)
        )

        # Commit changes and flash success message
        connection.commit()
        flash("Subject successfully added!", "success")

        # Redirect to the 'add_subject' page after successful form submission
        return redirect(url_for('subjects_blueprint.add_subject'))

    # Close cursor and connection
    cursor.close()
    connection.close()

    # Render the 'add_subject.html' template
    return render_template('subjects/add_subject.html', segment='add_subject')










# Route to edit an existing subject
@blueprint.route('/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
    # Connect to the database
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the subject data from the database
    cursor.execute('SELECT * FROM subjects WHERE subject_id = %s', (subject_id,))
    subject = cursor.fetchone()

    if not subject:
        flash("Subject not found!")
        return redirect(url_for('subjects_blueprint.subjects'))  # Redirect to subjects list page or home

    if request.method == 'POST':
        # Get the form data for subject details
        subject_code = request.form.get('subject_code')
        subject_name = request.form.get('subject_name')
        description = request.form.get('description')
        grade_level = request.form.get('grade_level')

        # Update the subject data in the database
        cursor.execute('''
            UPDATE subjects
            SET subject_code = %s, subject_name = %s, description = %s, grade_level = %s
            WHERE subject_id = %s
        ''', (subject_code, subject_name, description, grade_level, subject_id))

        # Commit the transaction
        connection.commit()

        flash("Subject updated successfully!", "success")
        return redirect(url_for('subjects_blueprint.subjects'))  # Redirect to subjects list or home

    cursor.close()
    connection.close()

    return render_template('subjects/edit_subject.html', subject=subject)













@blueprint.route('/delete_subject/<int:subjects_id>')
def delete_subject(subjects_id):
    """Deletes a subjects from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the subjects with the specified ID
        cursor.execute('DELETE FROM subjects WHERE subject_id = %s', (subjects_id,))
        connection.commit()
        flash("subjects deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('subjects_blueprint.subjects'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("subjects/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'subjects'

        return segment

    except:
        return None
