from apps.teachers import blueprint
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

from datetime import datetime
import pytz
def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)




# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@blueprint.route('/teachers')
def teachers():
    """Fetches all teachers and renders the manage teachers page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all teachers from the database
    cursor.execute('SELECT * FROM teachers ORDER BY last_name')
    teachers = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('teachers/teachers.html', teachers=teachers,segment='teachers')








@blueprint.route('/add_teacher', methods=['GET', 'POST'])
def add_teacher():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch subjects for dropdown (if needed)
    cursor.execute("SELECT * FROM subjects ORDER BY subject_name")
    subjects = cursor.fetchall()

    if request.method == 'POST':
        # Get form data
        teacher_number = request.form.get('teacher_number')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        other_name = request.form.get('other_name')
        name_sf = request.form.get('name_sf')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        subject_specialty = request.form.get('subject_specialty')
        grade_level = request.form.get('grade_level')
        contact_number = request.form.get('contact_number')
        email = request.form.get('email')
        hire_date = request.form.get('hire_date')
        address = request.form.get('address')
        status = request.form.get('status')

        # Check for duplicate teacher_number
        cursor.execute("SELECT 1 FROM teachers WHERE teacher_number = %s", (teacher_number,))
        if cursor.fetchone():
            flash(f"Teacher number {teacher_number} already exists.", "danger")
            cursor.close()
            connection.close()
            return render_template('teachers/add_teacher.html', subjects=subjects, segment='add_teacher')

        # Handle image upload
        image_filename = None
        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            image_filename = secure_filename(image_file.filename)
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image_file.save(image_path)

        # Handle signature image upload
        sign_image_filename = None
        sign_image_file = request.files.get('sign_image')
        if sign_image_file and allowed_file(sign_image_file.filename):
            sign_image_filename = secure_filename(sign_image_file.filename)
            sign_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], sign_image_filename)
            os.makedirs(os.path.dirname(sign_image_path), exist_ok=True)
            sign_image_file.save(sign_image_path)

        # Insert new teacher into the database
        cursor.execute(
            '''
            INSERT INTO teachers (
                teacher_number, first_name, other_name, last_name, name_sf,
                date_of_birth, gender, subject_specialty, grade_level,
                contact_number, email, hire_date, address, status,
                image, sign_image
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (
                teacher_number, first_name, other_name, last_name, name_sf,
                date_of_birth, gender, subject_specialty, grade_level,
                contact_number, email, hire_date, address, status,
                image_filename, sign_image_filename
            )
        )

        connection.commit()
        flash("Teacher successfully added!", "success")
        cursor.close()
        connection.close()
        return redirect(url_for('teachers_blueprint.add_teacher'))

    # GET request: render form
    cursor.close()
    connection.close()
    return render_template('teachers/add_teacher.html', subjects=subjects, segment='add_teacher')















@blueprint.route('/edit_teacher/<int:teacher_id>', methods=['GET', 'POST'])
def edit_teacher(teacher_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch the teacher data
    cursor.execute('SELECT * FROM teachers WHERE teacher_id = %s', (teacher_id,))
    teacher = cursor.fetchone()

    if not teacher:
        flash("Teacher not found!", "danger")
        cursor.close()
        connection.close()
        return redirect(url_for('teachers_blueprint.teachers'))

    # Fetch all subjects for dropdown
    cursor.execute('SELECT subject_name FROM subjects ORDER BY subject_name')
    subjects = cursor.fetchall()  # List of dicts like [{'subject_name': 'Math'}, ...]

    if request.method == 'POST':
        # Get form data
        teacher_number = request.form.get('teacher_number')  # Usually readonly but included
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')
        name_sf = request.form.get('name_sf')
        gender = request.form.get('gender')
        date_of_birth = request.form.get('date_of_birth')
        subject_specialty = request.form.get('subject_specialty')
        grade_level = request.form.get('grade_level')
        contact_number = request.form.get('contact_number')
        email = request.form.get('email')
        hire_date = request.form.get('hire_date')
        address = request.form.get('address')
        status = request.form.get('status')

        # Handle image uploads
        image_filename = teacher['image']
        sign_image_filename = teacher['sign_image']

        image_file = request.files.get('image')
        sign_image_file = request.files.get('sign_image')

        image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
        if not os.path.exists(image_folder):
            os.makedirs(image_folder)

        if image_file and image_file.filename and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{teacher_id}_{filename}"
            image_file.save(os.path.join(image_folder, image_filename))

        if sign_image_file and sign_image_file.filename and allowed_file(sign_image_file.filename):
            sign_filename = secure_filename(sign_image_file.filename)
            sign_image_filename = f"{teacher_id}_{sign_filename}"
            sign_image_file.save(os.path.join(image_folder, sign_image_filename))

        # Update DB
        cursor.execute('''
            UPDATE teachers
            SET teacher_number = %s,
                first_name = %s,
                other_name = %s,
                last_name = %s,
                name_sf = %s,
                gender = %s,
                date_of_birth = %s,
                subject_specialty = %s,
                grade_level = %s,
                contact_number = %s,
                email = %s,
                hire_date = %s,
                address = %s,
                status = %s,
                image = %s,
                sign_image = %s
            WHERE teacher_id = %s
        ''', (
            teacher_number, first_name, other_name, last_name, name_sf, gender, date_of_birth,
            subject_specialty, grade_level, contact_number, email, hire_date, address, status,
            image_filename, sign_image_filename, teacher_id
        ))

        connection.commit()
        cursor.close()
        connection.close()

        flash("Teacher updated successfully!", "success")
        return redirect(url_for('teachers_blueprint.teachers'))

    cursor.close()
    connection.close()

    return render_template('teachers/edit_teacher.html', teacher=teacher, subjects=subjects)















@blueprint.route('/delete_teacher/<int:teachers_id>')
def delete_teacher(teachers_id):
    """Deletes a teachers from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the teachers with the specified ID
        cursor.execute('DELETE FROM teachers WHERE teacher_id = %s', (teachers_id,))
        connection.commit()
        flash("teachers deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('teachers_blueprint.teachers'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("teachers/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'teachers'

        return segment

    except:
        return None
