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

from apps.classteacher_assign import blueprint
from apps import get_db_connection

import numpy as np


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']









@blueprint.route('/classteacher_assign')
def classteacher_assign():
    """
    Loads the classteacher Assignment interface:
    - Populates dropdowns: study years, streams, teachers, terms
    - Lists teachers and their classteacher assignments
    - Supports filtering by study year, stream, term, and user
    """

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown options
    def fetch_dropdown(query):
        cursor.execute(query)
        return cursor.fetchall()

    study_years = fetch_dropdown('SELECT year_id, year_name FROM study_year ORDER BY year_name')
    streams = fetch_dropdown('SELECT stream_id, stream_name FROM stream ORDER BY stream_name')
    terms = fetch_dropdown('SELECT term_id, term_name FROM terms ORDER BY term_name')
    users = fetch_dropdown("""
        SELECT id AS user_id, CONCAT(first_name, ' ', last_name) AS full_name
        FROM users
        ORDER BY full_name
    """)

    # Capture filter parameters
    filters = {
        'study_year': request.args.get('study_year', ''),
        'stream': request.args.get('stream', ''),
        'user_id': request.args.get('user_id', ''),
        'term_id': request.args.get('term_id', '')
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
    if filters['term_id']:
        where_clauses.append("sa.term_id = %s")
        sql_params.append(filters['term_id'])

    where_sql = " AND " + " AND ".join(where_clauses)

    # Main query: teachers and their assigned classteacher assignments
    assignment_query = f"""
        SELECT
            u.id AS user_id,
            CONCAT(u.first_name, ' ', u.last_name) AS full_name,
            CASE WHEN COUNT(sa.id) > 0 THEN 'Assigned' ELSE 'Not Assigned' END AS status,
            GROUP_CONCAT(
                CONCAT_WS(' - ',
                    t.term_name,
                    st.stream_name,
                    sy.year_name
                )
                ORDER BY sy.year_name, st.stream_name, t.term_name
                SEPARATOR '; '
            ) AS assigned_terms
        FROM users u
        LEFT JOIN classteacher_assignment sa ON sa.user_id = u.id
        LEFT JOIN terms t ON sa.term_id = t.term_id
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
        'classteacher_assign/classteacher_assign.html',
        segment='classteacher_assign',
        study_years=study_years,
        streams=streams,
        users=users,
        terms=terms,
        user_assignments=user_assignments,
        filters=filters
    )













from datetime import datetime

@blueprint.route('/action_classteacher_assign', methods=['POST'])
def action_classteacher_assign():
    assigned_by = session.get('id')

    user_id = request.form.get('user_id')
    stream_id = request.form.get('stream_id')
    year_id = request.form.get('year_id')
    term_id = request.form.get('term_id')

    if not user_id or not stream_id or not year_id or not term_id:
        flash('Teacher, Stream, Year, and Term are required.', 'warning')
        return redirect(url_for('classteacher_assign_blueprint.classteacher_assign'))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Check if an assignment exists with either this user_id OR stream_id
        cursor.execute("""
            SELECT id FROM classteacher_assignment
            WHERE user_id = %s OR stream_id = %s
            LIMIT 1
        """, (user_id, stream_id))

        existing = cursor.fetchone()

        if existing:
            flash('Assignment already exists for this teacher or stream.', 'warning')
            return redirect(url_for('classteacher_assign_blueprint.classteacher_assign'))

        # If no existing assignment, insert new assignment
        cursor.execute("""
            INSERT INTO classteacher_assignment (user_id, stream_id, year_id, term_id)
            VALUES (%s, %s, %s, %s)
        """, (user_id, stream_id, year_id, term_id))

        assignment_id = cursor.lastrowid

        # Log the insertion
        cursor.execute("""
            INSERT INTO classteacher_assignment_logs (
                assignment_id, user_id, stream_id, year_id, term_id,
                action, action_by, action_at, notes
            ) VALUES (%s, %s, %s, %s, %s, 'INSERT', %s, %s, %s)
        """, (
            assignment_id, user_id, stream_id, year_id, term_id,
            assigned_by, datetime.now(),
            'Inserted new classteacher assignment'
        ))

        connection.commit()
        flash('New assignment created and logged successfully.', 'success')

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred: {str(e)}", 'danger')

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('classteacher_assign_blueprint.classteacher_assign'))




























@blueprint.route('/classteacher_unassign', methods=['GET'])
def classteacher_unassign():
    """
    Display class teacher assignments with optional filters by year, stream, teacher, and term.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load filter dropdown options
    cursor.execute("SELECT year_id, year_name FROM study_year ORDER BY year_name")
    study_years = cursor.fetchall()

    cursor.execute("SELECT stream_id, stream_name FROM stream ORDER BY stream_name")
    streams = cursor.fetchall()

    cursor.execute("""
        SELECT id AS user_id, CONCAT(first_name, ' ', last_name) AS full_name
        FROM users
        WHERE LOWER(role) = 'teacher'
        ORDER BY full_name
    """)
    teachers = cursor.fetchall()

    cursor.execute("SELECT term_id, term_name FROM terms ORDER BY term_name")
    terms = cursor.fetchall()

    # Base query
    query = """
        SELECT
            sa.id AS id,
            u.id AS user_id,
            CONCAT(u.first_name, ' ', u.last_name) AS full_name,
            st.stream_id,
            st.stream_name,
            sy.year_id,
            sy.year_name,
            t.term_id,
            t.term_name
        FROM classteacher_assignment sa
        JOIN users u ON sa.user_id = u.id
        LEFT JOIN stream st ON sa.stream_id = st.stream_id
        LEFT JOIN study_year sy ON sa.year_id = sy.year_id
        LEFT JOIN terms t ON sa.term_id = t.term_id
        WHERE u.role = 'teacher'
    """

    params = []
    conditions = []

    # Filters from query parameters
    if study_year := request.args.get('year_id'):
        conditions.append("sa.year_id = %s")
        params.append(study_year)

    if stream := request.args.get('stream_id'):
        conditions.append("sa.stream_id = %s")
        params.append(stream)

    if user_id := request.args.get('user_id'):
        conditions.append("sa.user_id = %s")
        params.append(user_id)

    if term := request.args.get('term_id'):
        conditions.append("sa.term_id = %s")
        params.append(term)

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += """
        ORDER BY u.first_name, u.last_name, sy.year_name, st.stream_name, t.term_name
    """

    cursor.execute(query, tuple(params))
    class_teacher_assignments = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'classteacher_assign/classteacher_unassign.html',
        segment='classteacher_unassign',
        study_years=study_years,
        streams=streams,
        users=teachers,
        terms=terms,
        class_teacher_assignments=class_teacher_assignments,
        filters={
            'year_id': request.args.get('year_id', ''),
            'stream_id': request.args.get('stream_id', ''),
            'user_id': request.args.get('user_id', ''),
            'term_id': request.args.get('term_id', '')
        }
    )











@blueprint.route('/action_classteacher_unassign', methods=['POST'])
def action_classteacher_unassign():
    """
    Deletes selected classteacher assignments by their assignment ID.
    """
    assignment_ids = request.form.getlist('assignment_ids')

    if not assignment_ids:
        flash('No assignments selected for unassignment.', 'warning')
        return redirect(url_for('classteacher_assign_blueprint.classteacher_unassign'))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        for assignment_id in assignment_ids:
            cursor.execute("DELETE FROM classteacher_assignment WHERE id = %s", (assignment_id,))
        connection.commit()
        flash(f"{len(assignment_ids)} assignment(s) successfully unassigned.", 'success')
    except Exception as e:
        connection.rollback()
        flash(f"An error occurred while unassigning: {str(e)}", 'danger')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('classteacher_assign_blueprint.classteacher_unassign'))














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
