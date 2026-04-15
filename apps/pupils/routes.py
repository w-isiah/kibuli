from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, jsonify, send_file,current_app
)
from werkzeug.utils import secure_filename
from datetime import datetime
from jinja2 import TemplateNotFound
from io import BytesIO
import os
import random
import re
import logging
import pandas as pd
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation
import mysql.connector
from mysql.connector import Error

from apps.pupils import blueprint
from apps import get_db_connection

import numpy as np







@blueprint.route('/districts')
def show_districts():
    districts = current_app.config.get('DISTRICTS_DATA', [])
    return render_template('districts.html', districts=districts)






@blueprint.route('/api/districts', methods=['GET'])
def get_districts():
    """API endpoint to return district data as JSON."""
    districts = current_app.config.get('DISTRICTS_DATA', [])
    return jsonify(districts)




# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']





@blueprint.route('/pupils')
def pupils():
    """Filter pupils based on user input. No data is shown until filters are applied."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown options
    cursor.execute('SELECT year_id, year_name AS study_year FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
    class_list = cursor.fetchall()

    cursor.execute('SELECT term_id, term_name FROM terms ORDER BY term_name')
    terms = cursor.fetchall()

    cursor.execute('SELECT stream_id, stream_name FROM stream ORDER BY stream_name')
    stream_list = cursor.fetchall()

    # Get query parameters from form submission
    reg_no = request.args.get('reg_no', '').strip()
    index_number = request.args.get('index_number', '').strip()
    emis_number = request.args.get('emis_number', '').strip()
    name = request.args.get('name', '').strip()
    class_id = request.args.get('class_name', '').strip()
    stream_id = request.args.get('stream_id', '').strip()
    study_year_id = request.args.get('study_year', '').strip()
    term_id = request.args.get('term', '').strip()
    residential_status = request.args.get('residential_status', '').strip()
    nin_number = request.args.get('nin_number', '').strip()
    home_district = request.args.get('home_district', '').strip()

    # Determine if any filters are applied
    filters_applied = any([
        reg_no, index_number, emis_number, name, class_id, stream_id,
        study_year_id, term_id, residential_status,
        nin_number, home_district
    ])

    pupils = []
    params = {}
    filters = []

    def add_filter(column, param, value, use_like=False):
        if value:
            clause = f"{column} LIKE %({param})s" if use_like else f"{column} = %({param})s"
            filters.append(clause)
            params[param] = f"%{value}%" if use_like else value

    if filters_applied:
        add_filter("p.reg_no", "reg_no", reg_no, use_like=True)
        add_filter("p.index_number", "index_number", index_number, use_like=True)
        add_filter("p.emis_number", "emis_number", emis_number, use_like=True)
        add_filter("p.nin_number", "nin_number", nin_number, use_like=True)
        add_filter("p.home_district", "home_district", home_district, use_like=True)
        add_filter("p.class_id", "class_id", class_id)
        add_filter("p.stream_id", "stream_id", stream_id)
        add_filter("p.year_id", "study_year_id", study_year_id)
        add_filter("p.term_id", "term_id", term_id)
        add_filter("p.residential_status", "residential_status", residential_status)

        if name:
            filters.append("""
                (p.first_name LIKE %(name)s OR 
                 p.last_name LIKE %(name)s OR 
                 p.other_name LIKE %(name)s)
            """)
            params['name'] = f"%{name}%"

        query = f"""
            SELECT 
                p.pupil_id,
                p.reg_no,
                p.index_number,
                p.emis_number,
                CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
                p.gender,
                p.date_of_birth,
                p.admission_date,
                c.class_name,
                COALESCE(s.stream_name, 'None') AS stream_name,
                sy.year_name AS study_year,
                COALESCE(t.term_name, 'None') AS term_name,
                p.nin_number,
                p.residential_status,
                p.home_district,
                p.image
            FROM pupils p
            LEFT JOIN classes c ON p.class_id = c.class_id
            LEFT JOIN stream s ON p.stream_id = s.stream_id
            LEFT JOIN study_year sy ON p.year_id = sy.year_id
            LEFT JOIN terms t ON p.term_id = t.term_id
            WHERE {" AND ".join(filters)}
            ORDER BY p.last_name
        """


        cursor.execute(query, params)
        pupils = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'pupils/pupils.html',
        pupils=pupils,
        segment='pupils',
        class_list=class_list,
        stream_list=stream_list,
        terms=terms,
        study_years=study_years,
        filters={
            'reg_no': reg_no,
            'index_number': index_number,
            'emis_number': emis_number,
            'name': name,
            'class_name': class_id,
            'stream_id': stream_id,
            'study_year': study_year_id,
            'term': term_id,
            'residential_status': residential_status,
            'nin_number': nin_number,
            'home_district': home_district
        }
    )









@blueprint.route('/add_pupil', methods=['GET', 'POST'])
def add_pupil():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch classes and study years for form population
    cursor.execute('SELECT * FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()
    cursor.execute('SELECT * FROM classes ORDER BY class_name')
    classes = cursor.fetchall()

    if request.method == 'POST':
        # Retrieve form data
        reg_no = request.form.get('reg_no')
        first_name = request.form.get('first_name')
        other_name = request.form.get('other_name')
        last_name = request.form.get('last_name')
        nin_number = request.form.get('nin_number')
        emis_number = request.form.get('emis_number')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        class_id = request.form.get('class_id')  # this matches 'class_name' from form
        study_year = request.form.get('study_year')
        admission_date = request.form.get('admission_date')
        home_district = request.form.get('district')  # corrected typo from 'distirct'
        address = request.form.get('address')
        emergency_contact = request.form.get('emergency_contact')
        medical_info = request.form.get('medical_info')
        special_needs = request.form.get('special_needs')
        attendance_record = request.form.get('attendance_record')
        academic_performance = request.form.get('academic_performance')
        notes = request.form.get('notes')
        residential_status = request.form.get('residential_status')

        # Handle image upload
        image_file = request.files.get('image')
        image_filename = None

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = filename
            image_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
            os.makedirs(image_folder, exist_ok=True)
            image_path = os.path.join(image_folder, image_filename)
            image_file.save(image_path)

        # Insert into DB
        cursor.execute('''
            INSERT INTO pupils (
                reg_no, first_name, other_name, last_name, nin_number, emis_number,
                image, date_of_birth, gender, class_id, admission_date, year_id,
                home_district, address, emergency_contact, medical_info, special_needs,
                attendance_record, academic_performance, notes, residential_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            reg_no, first_name, other_name, last_name, nin_number, emis_number,
            image_filename, date_of_birth, gender, class_id, admission_date, study_year,
            home_district, address, emergency_contact, medical_info, special_needs,
            attendance_record, academic_performance, notes, residential_status
        ))

        connection.commit()
        flash("Pupil successfully added!", "success")

    cursor.close()
    connection.close()

    return render_template(
        'pupils/add_pupil.html',
        classes=classes,
        study_years=study_years,
        segment='add_pupil'
    )









@blueprint.route('/edit_pupil/<int:pupil_id>', methods=['GET', 'POST'])
def edit_pupil(pupil_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get pupil info
    cursor.execute('SELECT * FROM pupils WHERE pupil_id = %s', (pupil_id,))
    pupil = cursor.fetchone()

    if not pupil:
        flash("Pupil not found!", "danger")
        return redirect(url_for('pupils_blueprint.pupils'))

    # Get dropdown options
    cursor.execute('SELECT * FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT * FROM classes ORDER BY class_name')
    classes = cursor.fetchall()

    if request.method == 'POST':
        # Gather all form inputs
        form_fields = [
            'first_name', 'other_name', 'last_name', 'index_number','nin_number', 'emis_number',
            'date_of_birth', 'gender', 'study_year', 'admission_date',
            'district', 'address', 'emergency_contact', 'medical_info',
            'special_needs', 'attendance_record', 'academic_performance',
            'notes', 'residential_status'
        ]

        form_data = {field: request.form.get(field) for field in form_fields}

        # Handle file upload
        image_file = request.files.get('image')
        image_filename = pupil['image']  # Default to existing image

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_filename = f"{pupil_id}_{filename}"

            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/')
            os.makedirs(upload_folder, exist_ok=True)

            image_path = os.path.join(upload_folder, image_filename)
            try:
                image_file.save(image_path)
            except Exception as e:
                flash(f"Image upload failed: {e}", "danger")
                return redirect(request.url)

        # Perform update
        try:
            update_query = '''
                UPDATE pupils
                SET first_name = %s, other_name = %s, last_name = %s,
                    index_number=%s, nin_number = %s, emis_number = %s, date_of_birth = %s,
                    gender = %s, year_id = %s, admission_date = %s,
                    home_district = %s, address = %s, emergency_contact = %s,
                    medical_info = %s, special_needs = %s, attendance_record = %s,
                    academic_performance = %s, notes = %s, image = %s,
                    residential_status = %s
                WHERE pupil_id = %s
            '''

            cursor.execute(update_query, (
                form_data['first_name'], form_data['other_name'], form_data['last_name'],
                form_data['index_number'], form_data['nin_number'], form_data['emis_number'], form_data['date_of_birth'],
                form_data['gender'], form_data['study_year'],
                form_data['admission_date'], form_data['district'], form_data['address'],
                form_data['emergency_contact'], form_data['medical_info'],
                form_data['special_needs'], form_data['attendance_record'],
                form_data['academic_performance'], form_data['notes'],
                image_filename, form_data['residential_status'], pupil_id
            ))

            connection.commit()
            flash("Pupil updated successfully!", "success")
            return redirect(url_for('pupils_blueprint.pupils'))

        except Exception as e:
            flash(f"An error occurred while updating: {e}", "danger")

    # Close DB connection
    cursor.close()
    connection.close()

    return render_template(
        'pupils/edit_pupil.html',
        classes=classes,
        study_years=study_years,
        pupil=pupil
    )







@blueprint.route('/download_template', methods=['GET'])
def download_template():
    conn = get_db_connection()
    if not conn:
        return "Database connection failed", 500

    cursor = conn.cursor(dictionary=True)

    # Fetch dropdown values
    cursor.execute("SELECT class_name FROM classes ORDER BY class_name")
    classes = [row['class_name'] for row in cursor.fetchall()]

    cursor.execute("SELECT year_name FROM study_year ORDER BY year_name")
    study_years = [row['year_name'] for row in cursor.fetchall()]

    # Hardcoded dropdowns
    residential_statuses = ["Day", "Boarding"]
    gender_options = ["Male", "Female"]

    cursor.close()
    conn.close()

    # Create workbook and sheets
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pupils Template"

    # Headers for the main sheet
    headers = [
        "reg_no", "first_name", "other_name", "last_name", "nin_number", "emis_number",
        "date_of_birth", "gender", "class", "admission_date", "study_year",
        "home_district", "address", "emergency_contact", "medical_info", "special_needs",
        "attendance_record", "academic_performance", "notes", "residential_status"
    ]
    ws.append(headers)

    # Example row to show users date format (yyyy-mm-dd)
    example_row = [
        "REG123", "John", "A.", "Doe", "CM12345678", "EMIS001",
        "2008-05-15", "Male", "Primary 5", "2020-02-01", "2020",
        "Kampala", "123 Main St", "0700000000", "None", "None",
        "Good", "Above average", "No notes", "Day"
    ]
    ws.append(example_row)

    # Add hidden sheet for dropdown values
    dropdown_sheet = wb.create_sheet("drop_down_data")
    dropdown_sheet.append(["classes"] + classes)
    dropdown_sheet.append(["study_years"] + study_years)
    dropdown_sheet.append(["residential_statuses"] + residential_statuses)
    dropdown_sheet.append(["genders"] + gender_options)

    # Set data validations
    dv_class = DataValidation(type="list", formula1=f"=drop_down_data!$B$1:$Z$1", allow_blank=True)
    dv_year = DataValidation(type="list", formula1=f"=drop_down_data!$B$2:$Z$2", allow_blank=True)
    dv_res_status = DataValidation(type="list", formula1=f"=drop_down_data!$B$3:$Z$3", allow_blank=True)
    dv_gender = DataValidation(type="list", formula1=f"=drop_down_data!$B$4:$Z$4", allow_blank=True)

    # Add validations to worksheet
    ws.add_data_validation(dv_class)
    ws.add_data_validation(dv_year)
    ws.add_data_validation(dv_res_status)
    ws.add_data_validation(dv_gender)

    # Apply validations starting from row 3 (row 2 is example data)
    dv_gender.add("H3:H100")       # gender
    dv_class.add("I3:I100")        # class
    dv_year.add("K3:K100")         # study_year
    dv_res_status.add("T3:T100")   # residential_status

    # Hide the dropdown source sheet
    dropdown_sheet.sheet_state = 'hidden'

    # Return the workbook
    output = BytesIO()
    try:
        wb.save(output)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="Learners_template.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        return f"Error saving workbook: {e}", 500




# Utility functions
def get_existing_reg_nos():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT reg_no FROM pupils")
        return {str(row[0]).strip() for row in cursor.fetchall()}


def get_clean(value):
    return str(value).strip() if pd.notna(value) else ''


def safe_date(value):
    return pd.to_datetime(value).date() if pd.notna(value) else None


# Excel Upload Route
@blueprint.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if request.method == 'POST':
        file = request.files.get('file')

        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file format. Please upload a .xlsx Excel file.', 'danger')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            df = pd.read_excel(file_path)
            required_columns = [
                "reg_no", "first_name", "other_name", "last_name", "nin_number", "emis_number",
                "date_of_birth", "gender", "class", "admission_date", "study_year",
                "home_district", "address", "emergency_contact", "medical_info", "special_needs",
                "attendance_record", "academic_performance", "notes", "residential_status"
            ]

            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                flash(f"Missing required columns: {', '.join(missing_cols)}", 'danger')
                return redirect(request.url)

            existing_reg_nos = get_existing_reg_nos()
            processed_data, errors, existing_db_dupes, local_dupes = validate_excel_data(df, existing_reg_nos)

            if existing_db_dupes:
                flash(f"Skipped existing reg_no(s): {', '.join(existing_db_dupes)}", 'warning')
            if local_dupes:
                flash(f"Skipped duplicate reg_no(s) in file: {', '.join(local_dupes)}", 'warning')
            if errors:
                flash('Errors encountered:\n' + '\n'.join(errors), 'danger')
                return redirect(request.url)

            insert_into_database(processed_data)
            flash(f"{len(processed_data)} record(s) uploaded successfully!", 'success')

        except pd.errors.EmptyDataError:
            flash('Uploaded Excel file is empty.', 'danger')
        except Exception as e:
            flash(f'Error processing the file: {str(e)}', 'danger')

        return redirect(url_for('pupils_blueprint.upload_excel'))

    return render_template('pupils/upload_excel.html')


# Data validation
def validate_excel_data(df, existing_db_reg_nos=None):
    processed_data = []
    errors = []
    existing_reg_nos = []
    duplicate_reg_nos = []
    seen_reg_nos = set()

    required_columns = {
        'reg_no', 'first_name', 'last_name', 'gender', 'class',
        'study_year', 'date_of_birth', 'admission_date'
    }

    if existing_db_reg_nos is None:
        existing_db_reg_nos = get_existing_reg_nos()

    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT class_name, class_id FROM classes")
        class_map = {str(row[0]).strip(): int(row[1]) for row in cursor.fetchall()}

        cursor.execute("SELECT year_name, year_id FROM study_year")
        year_map = {str(row[0]).strip(): int(row[1]) for row in cursor.fetchall()}

        for index, row in df.iterrows():
            if row.isnull().all():
                continue

            reg_no = get_clean(row.get('reg_no'))
            class_name = get_clean(row.get('class'))
            year_name = get_clean(row.get('study_year'))

            if not reg_no or not class_name or not year_name:
                errors.append(f"Row {index + 2}: Missing required fields.")
                continue

            if reg_no in seen_reg_nos:
                duplicate_reg_nos.append(reg_no)
                continue
            seen_reg_nos.add(reg_no)

            if reg_no in existing_db_reg_nos:
                existing_reg_nos.append(reg_no)
                continue

            class_id = class_map.get(class_name)
            year_id = year_map.get(year_name)

            if not class_id:
                errors.append(f"Row {index + 2}: Invalid class '{class_name}'.")
            if not year_id:
                errors.append(f"Row {index + 2}: Invalid study year '{year_name}'.")

            if class_id and year_id:
                processed_data.append({
                    'reg_no': reg_no,
                    'first_name': get_clean(row.get('first_name')),
                    'other_name': get_clean(row.get('other_name')),
                    'last_name': get_clean(row.get('last_name')),
                    'nin_number': get_clean(row.get('nin_number')),
                    'emis_number': get_clean(row.get('emis_number')),
                    'date_of_birth': safe_date(row.get('date_of_birth')),
                    'gender': get_clean(row.get('gender')),
                    'class_id': class_id,
                    'admission_date': safe_date(row.get('admission_date')),
                    'year_id': year_id,
                    'home_district': get_clean(row.get('home_district')),
                    'address': get_clean(row.get('address')),
                    'emergency_contact': get_clean(row.get('emergency_contact')),
                    'medical_info': get_clean(row.get('medical_info')),
                    'special_needs': get_clean(row.get('special_needs')),
                    'attendance_record': get_clean(row.get('attendance_record')),
                    'academic_performance': get_clean(row.get('academic_performance')),
                    'notes': get_clean(row.get('notes')),
                    'residential_status': get_clean(row.get('residential_status')).lower()
                })

    return processed_data, errors, existing_reg_nos, duplicate_reg_nos








def insert_into_database(processed_data):
    if not processed_data:
        print("No data to insert.")
        return

    insert_query = """
        INSERT INTO `pupils` (
            `reg_no`, `first_name`, `other_name`, `last_name`,
            `nin_number`, `emis_number`, `image`, `date_of_birth`,
            `gender`, `class_id`, `admission_date`, `year_id`,
            `home_district`, `address`, `emergency_contact`, `medical_info`,
            `special_needs`, `attendance_record`, `academic_performance`,
            `notes`, `residential_status`
        ) VALUES (
            %(reg_no)s, %(first_name)s, %(other_name)s, %(last_name)s,
            %(nin_number)s, %(emis_number)s, NULL, %(date_of_birth)s,
            %(gender)s, %(class_id)s, %(admission_date)s, %(year_id)s,
            %(home_district)s, %(address)s, %(emergency_contact)s, %(medical_info)s,
            %(special_needs)s, %(attendance_record)s, %(academic_performance)s,
            %(notes)s, %(residential_status)s
        )
    """

    inserted_count = 0
    failed_rows = []

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            for idx, data in enumerate(processed_data, start=1):
                try:
                    for date_field in ['date_of_birth', 'admission_date']:
                        if isinstance(data[date_field], pd.Timestamp):
                            data[date_field] = data[date_field].date()

                    cursor.execute(insert_query, data)
                    inserted_count += 1

                except Exception as row_err:
                    failed_rows.append((idx, data.get('reg_no'), str(row_err)))

            connection.commit()

    except Exception as e:
        print("Fatal database error:", e)
        return

    print(f"{inserted_count} record(s) inserted successfully.")
    if failed_rows:
        print("Some rows failed to insert:")
        for row_num, reg_no, err in failed_rows:
            print(f"  Row {row_num} (reg_no={reg_no}): {err}")









@blueprint.route('/delete_pupil', methods=['POST'])
def delete_pupil():
    """Deletes selected pupils from the database."""
    pupil_ids = request.form.getlist('pupil_ids')
    
    if not pupil_ids:
        flash("No pupils selected for deletion.", "warning")
        return redirect(url_for('pupils_blueprint.pupils'))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        placeholders = ', '.join(['%s'] * len(pupil_ids))
        cursor.execute(f"DELETE FROM pupils WHERE pupil_id IN ({placeholders})", tuple(pupil_ids))
        connection.commit()
        flash(f"Deleted {cursor.rowcount} pupil(s) successfully.", "success")
    except Exception as e:
        flash(f"Error deleting pupil(s): {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('pupils_blueprint.pupils'))








@blueprint.route('/<template>')
def route_template(template):
    """
    Renders dynamic templates from the 'home' folder.
    """
    try:
        if not template.endswith('.html'):
            template += '.html'
        
        segment = get_segment(request)
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        logging.error(f"Template {template} not found")
        return render_template('home/page-404.html', segment=segment), 404

    except Exception as e:
        logging.error(f"Error rendering template {template}: {str(e)}")
        return render_template('home/page-500.html', segment=segment), 500

def get_segment(request):
    """
    Extracts the last part of the URL path to identify the current page.
    """
    segment = request.path.strip('/').split('/')[-1]
    if not segment:
        segment = 'pupils'
    return segment
