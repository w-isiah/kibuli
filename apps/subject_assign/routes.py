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

from apps.subject_assign import blueprint
from apps import get_db_connection

import numpy as np


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']









@blueprint.route('/subject_assign')
def subject_assign():
    """
    Loads the Subject Assignment interface:
    - Populates dropdowns: study years, streams, teachers, subjects
    - Lists teachers and their subject assignments
    - Supports filtering by study year, stream, subject, and user
    """

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown options
    def fetch_dropdown(query):
        cursor.execute(query)
        return cursor.fetchall()

    study_years = fetch_dropdown('SELECT year_id, year_name FROM study_year ORDER BY year_name')
    streams = fetch_dropdown('SELECT stream_id, stream_name FROM stream ORDER BY stream_name')
    subjects = fetch_dropdown('SELECT subject_id, subject_name FROM subjects ORDER BY subject_name')
    users = fetch_dropdown("""
        SELECT id AS user_id, CONCAT(first_name, ' ', last_name) AS full_name
        FROM users
        WHERE role = 'teacher' OR role1 = 'teacher'
        ORDER BY full_name
    """)

    # Capture filter parameters
    filters = {
        'study_year': request.args.get('study_year', ''),
        'stream': request.args.get('stream', ''),
        'user_id': request.args.get('user_id', ''),
        'subject_id': request.args.get('subject_id', '')
    }

    # Build WHERE clause
    where_clauses = ["(u.role = 'teacher' OR u.role1 = 'teacher')"]
    sql_params = []

    if filters['study_year']:
        where_clauses.append("sa.year_id = %s")
        sql_params.append(filters['study_year'])
    if filters['stream']:
        where_clauses.append("sa.stream_id = %s")
        sql_params.append(filters['stream'])
    if filters['user_id']:
        where_clauses.append("u.id = %s")
        sql_params.append(filters['user_id'])
    if filters['subject_id']:
        where_clauses.append("sa.subject_id = %s")
        sql_params.append(filters['subject_id'])

    where_sql = " AND " + " AND ".join(where_clauses)

    # Main query: teachers and their assigned subjects
    assignment_query = f"""
        SELECT
            u.id AS user_id,
            CONCAT(u.first_name, ' ', u.last_name) AS full_name,
            CASE WHEN COUNT(sa.id) > 0 THEN 'Assigned' ELSE 'Not Assigned' END AS status,
            GROUP_CONCAT(
                CONCAT_WS(' - ',
                    s.subject_name,
                    st.stream_name,
                    sy.year_name
                )
                ORDER BY sy.year_name, st.stream_name, s.subject_name
                SEPARATOR '; '
            ) AS assigned_subjects
        FROM users u
        LEFT JOIN subject_assignment sa ON sa.user_id = u.id
        LEFT JOIN subjects s ON sa.subject_id = s.subject_id
        LEFT JOIN stream st ON sa.stream_id = st.stream_id
        LEFT JOIN study_year sy ON sa.year_id = sy.year_id
        WHERE 1=1 {where_sql}
        GROUP BY u.id
        ORDER BY u.first_name, u.last_name
    """

    cursor.execute(assignment_query, tuple(sql_params))
    user_assignments = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'subject_assign/subject_assign.html',
        segment='subject_assign',
        study_years=study_years,
        streams=streams,
        users=users,
        subjects=subjects,
        user_assignments=user_assignments,
        filters=filters
    )












@blueprint.route('/action_subject_assign', methods=['POST'])
def action_subject_assign():
    assigned_by = session.get('id')

    # Match names with your frontend form inputs!
    selected_user_ids = request.form.getlist('user_ids')
    subject_id = request.form.get('subject_id')
    stream_id = request.form.get('stream_id')
    year_id = request.form.get('year_id')

    print("Selected user_ids:", selected_user_ids)
    print("Subject ID:", subject_id)
    print("Stream ID:", stream_id)
    print("Year ID:", year_id)

    if not selected_user_ids:
        flash('No teachers selected. Please select at least one teacher.', 'warning')
        return redirect(url_for('subject_assign_blueprint.subject_assign'))

    if not subject_id or not stream_id or not year_id:
        flash('Subject, Stream, and Study Year are required.', 'warning')
        return redirect(url_for('subject_assign_blueprint.subject_assign'))

    connection = get_db_connection()
    cursor = connection.cursor()
    successful = 0

    try:
        for user_id in selected_user_ids:
            cursor.execute("""
                SELECT 1 FROM subject_assignment
                WHERE subject_id = %s AND stream_id = %s AND year_id = %s AND user_id = %s
            """, (subject_id, stream_id, year_id, user_id))
            if cursor.fetchone():
                continue

            cursor.execute("""
                INSERT INTO subject_assignment (subject_id, stream_id, year_id, user_id)
                VALUES (%s, %s, %s, %s)
            """, (subject_id, stream_id, year_id, user_id))
            successful += 1

        connection.commit()

        if successful > 0:
            flash(f"{successful} assignment(s) successfully created.", "success")
        else:
            flash("No new assignments were created (duplicates skipped).", "info")

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('subject_assign_blueprint.subject_assign'))

























@blueprint.route('/subject_unassign', methods=['GET'])
def subject_unassign():
    """
    Display subject assignments for users with role 'teacher',
    with optional filters by study year, stream, teacher, and subject.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # --- Load filter dropdown options ---
    cursor.execute("SELECT year_id, year_name FROM study_year ORDER BY year_name")
    study_years = cursor.fetchall()

    cursor.execute("SELECT stream_id, stream_name FROM stream ORDER BY stream_name")
    streams = cursor.fetchall()

    cursor.execute("""
        SELECT id AS user_id, CONCAT(first_name, ' ', last_name) AS full_name
        FROM users
        
        ORDER BY full_name
    """)
    teachers = cursor.fetchall()

    cursor.execute("SELECT subject_id, subject_name FROM subjects ORDER BY subject_name")
    subjects = cursor.fetchall()

    # --- Base query ---
    query = """
        SELECT
            sa.id AS assignment_id,
            u.id AS user_id,
            u.role as role,
            CONCAT(u.first_name, ' ', u.last_name) AS full_name,
            s.subject_id,
            s.subject_name,
            st.stream_id,
            st.stream_name,
            sy.year_id,
            sy.year_name
        FROM subject_assignment sa
        JOIN users u ON sa.user_id = u.id
        LEFT JOIN subjects s ON sa.subject_id = s.subject_id
        LEFT JOIN stream st ON sa.stream_id = st.stream_id
        LEFT JOIN study_year sy ON sa.year_id = sy.year_id
        WHERE u.role= 'teacher'
    """

    params = []
    conditions = []

    # --- Optional filters from query parameters ---
    if study_year := request.args.get('study_year'):
        conditions.append("sa.year_id = %s")
        params.append(study_year)

    if stream := request.args.get('stream'):
        conditions.append("sa.stream_id = %s")
        params.append(stream)

    if user_id := request.args.get('user_id'):
        conditions.append("sa.user_id = %s")
        params.append(user_id)

    if subject_id := request.args.get('subject_id'):
        conditions.append("sa.subject_id = %s")
        params.append(subject_id)

    # --- Append conditions to query ---
    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += """
        ORDER BY u.first_name, u.last_name, sy.year_name, st.stream_name, s.subject_name
    """

    # --- Execute query ---
    cursor.execute(query, tuple(params))
    user_assignments = cursor.fetchall()

    cursor.close()
    connection.close()

    # --- Render template ---
    return render_template(
        'subject_assign/subject_unassign.html',
        segment='subject_unassign',
        study_years=study_years,
        streams=streams,
        users=teachers,
        subjects=subjects,
        user_assignments=user_assignments,
        filters={
            'study_year': request.args.get('study_year', ''),
            'stream': request.args.get('stream', ''),
            'user_id': request.args.get('user_id', ''),
            'subject_id': request.args.get('subject_id', '')
        }
    )











@blueprint.route('/action_subject_unassign', methods=['POST'])
def action_subject_unassign():
    """
    Deletes selected subject assignments by their assignment ID (primary key).
    """
    assignment_ids = request.form.getlist('assignment_ids')

    if not assignment_ids:
        flash('No assignments selected for unassignment.', 'warning')
        return redirect(url_for('subject_assign_blueprint.subject_unassign'))

    connection = get_db_connection()
    cursor = connection.cursor()
    successful = 0

    try:
        for assignment_id in assignment_ids:
            cursor.execute("DELETE FROM subject_assignment WHERE id = %s", (assignment_id,))
            successful += 1

        connection.commit()

        flash(f"{successful} assignment(s) successfully unassigned.", "success")

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred while unassigning: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('subject_assign_blueprint.subject_unassign'))
















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
