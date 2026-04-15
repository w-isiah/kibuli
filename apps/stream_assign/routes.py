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

from apps.stream_assign import blueprint
from apps import get_db_connection

import numpy as np


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']





@blueprint.route('/stream_assign')
def stream_assign():
    """Fetch and filter pupils by Reg No, Name, Class, Study Year, Term, and Stream."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute('SELECT year_id, year_name AS study_year FROM study_year ORDER BY year_name')
    study_years = cursor.fetchall()

    cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
    class_list = cursor.fetchall()

    cursor.execute('SELECT term_id, term_name FROM terms ORDER BY term_name')
    terms = cursor.fetchall()

    cursor.execute('''
        SELECT 
            s.stream_id,
            s.stream_name,
            c.class_id,
            c.class_name
        FROM stream s
        JOIN classes c ON s.class_id = c.class_id
        ORDER BY s.stream_name
    ''')
    streams = cursor.fetchall()

    # Get form filter values
    reg_no = request.args.get('reg_no', '').strip()
    name = request.args.get('name', '').strip()
    class_id = request.args.get('class_id', '').strip()
    study_year_id = request.args.get('study_year', '').strip()
    term_id = request.args.get('term', '').strip()
    stream_id = request.args.get('stream', '').strip()

    filters = []
    params = {}

    if reg_no:
        filters.append("p.reg_no LIKE %(reg_no)s")
        params['reg_no'] = f"%{reg_no}%"

    if name:
        filters.append("(p.first_name LIKE %(name)s OR p.last_name LIKE %(name)s)")
        params['name'] = f"%{name}%"

    if class_id:
        filters.append("p.class_id = %(class_id)s")
        params['class_id'] = class_id

    if study_year_id:
        filters.append("p.year_id = %(study_year_id)s")
        params['study_year_id'] = study_year_id

    if term_id:
        filters.append("p.term_id = %(term_id)s")
        params['term_id'] = term_id

    if stream_id:
        filters.append("p.stream_id = %(stream_id)s")
        params['stream_id'] = stream_id

    pupils = []
    if filters:
        query = f'''
            SELECT 
                p.pupil_id,
                p.reg_no,
                TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) AS full_name,
                p.gender,
                p.image,
                p.date_of_birth,
                sy.year_name AS study_year,
                c.class_name,
                p.class_id, 
                COALESCE(t.term_name, 'None') AS term_name,
                COALESCE(s.stream_name, 'None') AS stream_name
            FROM pupils p
            JOIN study_year sy ON p.year_id = sy.year_id
            JOIN classes c ON p.class_id = c.class_id
            LEFT JOIN terms t ON p.term_id = t.term_id
            LEFT JOIN stream s ON p.stream_id = s.stream_id
            WHERE {' AND '.join(filters)}
            ORDER BY p.last_name
        '''
        cursor.execute(query, params)
        pupils = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'stream_assign/stream_assign.html',
        pupils=pupils,
        segment='pupils',
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        streams=streams,
        filters={
            'reg_no': reg_no,
            'name': name,
            'class_id': class_id,
            'study_year': study_year_id,
            'term': term_id,
            'stream': stream_id
        }
    )












from datetime import datetime
import pytz


def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

@blueprint.route('/stream_term_assign', methods=['POST'])
def stream_term_assign():
    assigned_by = session.get('id')
    selected_pupil_ids = request.form.getlist('pupil_ids')
    stream_id = request.form.get('stream_id')
    term_id = request.form.get('term')

    if not selected_pupil_ids:
        flash('No pupils were selected.', 'warning')
        return redirect(url_for('stream_assign_blueprint.stream_assign'))

    if not term_id:
        flash('No term was selected.', 'warning')
        return redirect(url_for('stream_assign_blueprint.stream_assign'))

    if not stream_id:
        flash('No stream was selected. Please click on a pupil row to select a stream.', 'warning')
        return redirect(url_for('stream_assign_blueprint.stream_assign'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    successful = 0

    try:
        for pupil_id in selected_pupil_ids:
            # Fetch current data
            cursor.execute("SELECT term_id, stream_id, class_id, year_id FROM pupils WHERE pupil_id = %s", (pupil_id,))
            result = cursor.fetchone()

            if not result:
                flash(f'Pupil {pupil_id} not found, skipping.', 'warning')
                continue

            current_term = str(result['term_id'])
            current_stream = str(result['stream_id'])

            if current_term == str(term_id) and current_stream == str(stream_id):
                flash(f'Pupil {pupil_id} is already assigned to this stream and term.', 'info')
                continue

            # Update pupils table
            cursor.execute("""
                UPDATE pupils
                SET term_id = %s, stream_id = %s
                WHERE pupil_id = %s
            """, (term_id, stream_id, pupil_id))
            successful += 1

            # Log the change to enrollment_history
            cursor.execute("""
                INSERT INTO enrollment_history (
                    pupil_id, class_id, stream_id, term_id, year_id,
                    action_type, registered_by, notes, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                pupil_id,
                result['class_id'],
                stream_id,
                term_id,
                result['year_id'],
                'update',
                assigned_by,
                'Stream and/or term reassignment',
                get_kampala_time()
            ))

        connection.commit()

        if successful > 0:
            flash(f"{successful} pupil(s) successfully assigned.", "success")

    except Exception as e:
        connection.rollback()
        flash(f'Error during assignment: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('stream_assign_blueprint.stream_assign'))















@blueprint.route('/streams_data')
def streams_data():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute('''
        SELECT 
            s.stream_id,
            s.stream_name,
            c.class_id,
            c.class_name
        FROM stream s
        JOIN classes c ON s.class_id = c.class_id
        ORDER BY s.stream_name
    ''')
    streams = cursor.fetchall()

    # No need to manually convert if using dictionary cursor
    return jsonify(streams)










@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("pupils/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'pupils'

        return segment

    except:
        return None
