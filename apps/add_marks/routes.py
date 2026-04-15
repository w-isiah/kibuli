from apps.add_marks import blueprint
from flask import render_template, request, redirect, url_for, flash, session
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
import numpy as np 
from datetime import datetime
import pytz
from flask import request, session, flash, redirect, url_for




def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)



from mysql.connector import Error

@blueprint.route('/add_marks', methods=['GET'])
def add_marks():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # 1. Standard Dropdown Data
    dropdown_queries = {
        'class_list': "SELECT * FROM classes",
        'study_years': "SELECT * FROM study_year",
        'terms': "SELECT * FROM terms",
        'assessments': "SELECT * FROM assessment",
        'subjects': "SELECT * FROM subjects",
        'streams': "SELECT * FROM stream"
    }
    
    dropdown_data = {}
    for key, sql in dropdown_queries.items():
        cursor.execute(sql)
        dropdown_data[key] = cursor.fetchall()

    # 2. Get Filters
    filters = {
        'class_id': request.args.get('class_id', type=int),
        'year_id': request.args.get('year_id', type=int),
        'term_id': request.args.get('term_id', type=int),
        'subject_id': request.args.get('subject_id', type=int),
        'assessment_name': request.args.get('assessment_name', type=str),
        'stream_id': request.args.get('stream_id', type=int),
        'reg_no': request.args.get('reg_no', type=str)
    }

    # 3. Validation: If core filters are missing, return empty list
    if not all([filters['year_id'], filters['term_id'], filters['subject_id'], filters['assessment_name']]):
        return render_template('add_marks/add_marks.html', add_marks=[], **dropdown_data, **filters)

    # 4. Main Query: Find pupils AND their existing scores (if any)
    # This uses a LEFT JOIN on scores so pupils stay in the list even after you add a mark
    query = """
        SELECT 
            p.pupil_id, p.reg_no, p.class_id, p.stream_id,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            str.stream_name,
            %s AS year_id,
            %s AS term_id,
            %s AS subject_id,
            a.assessment_id,
            a.assessment_name,
            s.Mark AS existing_mark,
            s.notes AS existing_remark
        FROM pupils p
        LEFT JOIN stream str ON p.stream_id = str.stream_id
        CROSS JOIN assessment a ON a.assessment_name = %s
        LEFT JOIN scores s ON s.reg_no = p.reg_no 
            AND s.year_id = %s 
            AND s.term_id = %s 
            AND s.subject_id = %s 
            AND s.assessment_id = a.assessment_id
        WHERE 1=1
    """
    
    params = [
        filters['year_id'], filters['term_id'], filters['subject_id'], 
        filters['assessment_name'], filters['year_id'], filters['term_id'], filters['subject_id']
    ]

    # Append optional filters
    if filters['class_id']:
        query += " AND p.class_id = %s"
        params.append(filters['class_id'])
    if filters['stream_id']:
        query += " AND p.stream_id = %s"
        params.append(filters['stream_id'])
    if filters['reg_no']:
        query += " AND p.reg_no = %s"
        params.append(filters['reg_no'])

    query += " ORDER BY p.last_name, p.first_name"
    
    cursor.execute(query, params)
    add_marks = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('add_marks/add_marks.html', 
                           add_marks=add_marks, 
                           **dropdown_data, 
                           **filters, 
                           segment='add_marks')










@blueprint.route('/teacher_add_marks', methods=['GET', 'POST'])
def teacher_add_marks():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    user_id = session.get('id')  # Get logged-in teacher ID
    if not user_id:
        flash('You must be logged in as a teacher to access this page.', 'danger')
        return redirect(url_for('authentication_blueprint.login'))

    # Load dropdowns based on assignments only
    # Classes (still unfiltered unless needed)
    cursor.execute("""
        SELECT DISTINCT c.class_id, c.class_name
    FROM classes c
    JOIN stream s ON s.class_id = c.class_id
    JOIN subject_assignment sa ON sa.stream_id = s.stream_id
    WHERE sa.user_id = %s
    """, (user_id,))
    class_list = cursor.fetchall()



    # Study years assigned to this teacher
    cursor.execute("""
        SELECT DISTINCT y.year_id, y.year_name
        FROM study_year y
        JOIN subject_assignment sa ON sa.year_id = y.year_id
        WHERE sa.user_id = %s
    """, (user_id,))
    study_years = cursor.fetchall()

    # Terms (likely fixed for all, can be filtered similarly if needed)
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    # Assessments (assumed to be global, keep all)
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Subjects assigned to this teacher
    cursor.execute("""
        SELECT DISTINCT s.subject_id, s.subject_name
        FROM subjects s
        JOIN subject_assignment sa ON sa.subject_id = s.subject_id
        WHERE sa.user_id = %s
    """, (user_id,))
    subjects = cursor.fetchall()

    # Streams assigned to this teacher
    cursor.execute("""
        SELECT DISTINCT str.stream_id, str.stream_name
        FROM stream str
        JOIN subject_assignment sa ON sa.stream_id = str.stream_id
        WHERE sa.user_id = %s
    """, (user_id,))
    streams = cursor.fetchall()

    cursor.execute("""
    SELECT DISTINCT p.*
    FROM pupils p
    JOIN subject_assignment sa 
        ON p.stream_id = sa.stream_id
       AND sa.year_id = p.year_id
    WHERE sa.user_id = %s
    """, (user_id,))
    pupils = cursor.fetchall()


    # Filter parameters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)
    pupil_name = request.args.get('pupil_name', type=str)
    reg_no = request.args.get('reg_no', type=str)

    if not (year_id and term_id and subject_id and assessment_name):
        cursor.close()
        connection.close()
        return render_template('add_marks/teacher_add_marks.html',
            add_marks=[], class_list=class_list, study_years=study_years,
            terms=terms, subjects=subjects, assessments=assessments,
            streams=streams, pupils=pupils,
            selected_class_id=class_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name,
            selected_subject_id=subject_id,
            selected_stream_id=stream_id,
            selected_pupil_name=pupil_name,
            entered_reg_no=reg_no,
            segment='add_marks'
        )

    query = """
        SELECT 
            p.reg_no,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            p.pupil_id,
            y.year_name,
            t.term_name,
            str.stream_name,
            sub.subject_name,
            a.assessment_name,
            p.class_id,
            p.stream_id,
            %s AS year_id,
            %s AS term_id,
            (SELECT assessment_id FROM assessment WHERE assessment_name = %s LIMIT 1) AS assessment_id,
            %s AS subject_id
        FROM pupils p
        INNER JOIN subject_assignment sa ON sa.stream_id = p.stream_id 
            AND sa.subject_id = %s
            AND sa.year_id = %s
            AND sa.user_id = %s
        LEFT JOIN stream str ON p.stream_id = str.stream_id
        LEFT JOIN study_year y ON y.year_id = %s
        LEFT JOIN terms t ON t.term_id = %s
        LEFT JOIN subjects sub ON sub.subject_id = %s
        LEFT JOIN assessment a ON a.assessment_name = %s
        WHERE NOT EXISTS (
            SELECT 1 FROM scores s
            WHERE s.reg_no = p.reg_no
              AND s.year_id = %s
              AND s.term_id = %s
              AND s.subject_id = %s
              AND s.assessment_id = (SELECT assessment_id FROM assessment WHERE assessment_name = %s LIMIT 1)
        )
    """

    query_params = [
        year_id, term_id, assessment_name, subject_id,  # SELECT fields
        subject_id, year_id, user_id,                   # subject_assignment join
        year_id, term_id, subject_id, assessment_name,  # LEFT JOINs
        year_id, term_id, subject_id, assessment_name   # Subquery for scores
    ]

    if class_id:
        query += " AND p.class_id = %s"
        query_params.append(class_id)
    if stream_id:
        query += " AND p.stream_id = %s"
        query_params.append(stream_id)
    if pupil_name:
        query += " AND TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) LIKE %s"
        query_params.append(f"%{pupil_name}%")
    if reg_no:
        query += " AND p.reg_no = %s"
        query_params.append(reg_no)

    query += " ORDER BY p.last_name, p.first_name, p.other_name"

    cursor.execute(query, query_params)
    add_marks = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('add_marks/teacher_add_marks.html',
        add_marks=add_marks,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        subjects=subjects,
        assessments=assessments,
        streams=streams,
        pupils=pupils,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_subject_id=subject_id,
        selected_stream_id=stream_id,
        selected_pupil_name=pupil_name,
        entered_reg_no=reg_no,
        segment='add_marks'
    )








@blueprint.route('/action_add_marks', methods=['POST'])
def action_add_marks():
    user_id = session.get('id')
    if not user_id:
        flash("You must be logged in to add marks.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    form_data = request.form
    submitted_pupil_id = form_data.get('submit_add')  
    all_pupil_ids = form_data.getlist('pupil_ids')
    target_ids = [submitted_pupil_id] if submitted_pupil_id else all_pupil_ids

    if not target_ids:
        flash("No pupils selected.", "warning")
        return redirect(request.referrer)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    success_count = 0
    skipped_pupils = []
    errors = []
    kampala_time = get_kampala_time()

    try:
        for p_id in target_ids:
            # 1. Validation: Check if mark is provided and valid
            mark_str = form_data.get(f"add_marks[{p_id}]", "").strip()
            if not mark_str:
                continue 
            
            try:
                mark = float(mark_str)
                if not (0 <= mark <= 100):
                    errors.append(f"Mark {mark} out of range for ID {p_id}.")
                    continue
            except ValueError:
                errors.append(f"Invalid number for ID {p_id}.")
                continue

            # 2. Metadata Extraction
            def get_val(field): return form_data.get(f"{field}[{p_id}]")
            
            reg_no = get_val("reg_no")
            s_id = get_val("subject_id")
            a_id = get_val("assessment_id")
            t_id = get_val("term_id")
            y_id = get_val("year_id")
            c_id = get_val("class_id")
            st_id = get_val("stream_id")
            remark = form_data.get(f"add_remarks[{p_id}]", "").strip()

            # 3. STRICT CHECK: Does a mark already exist?
            # We check the unique constraints before attempting any insert
            cursor.execute("""
                SELECT score_id FROM scores 
                WHERE reg_no=%s AND subject_id=%s AND assessment_id=%s AND term_id=%s AND year_id=%s
            """, (reg_no, s_id, a_id, t_id, y_id))
            
            if cursor.fetchone():
                # If a record exists, we skip this student
                skipped_pupils.append(reg_no)
                continue

            # 4. INSERT ONLY: Standard insert without update clause
            insert_query = """
                INSERT INTO scores (
                    user_id, reg_no, class_id, stream_id, term_id, year_id,
                    assessment_id, subject_id, Mark, notes, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                user_id, reg_no, c_id, st_id, t_id, y_id, a_id, s_id, mark, remark, kampala_time, kampala_time
            ))
            
            # 5. Log the new entry
            score_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO add_score_logs (
                    score_id, user_id, reg_no, class_id, stream_id, term_id,
                    year_id, assessment_id, subject_id, new_mark, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (score_id, user_id, reg_no, c_id, st_id, t_id, y_id, a_id, s_id, mark, remark, kampala_time))

            success_count += 1

        connection.commit()

        # Feedback Logic
        if success_count > 0:
            flash(f"Successfully added {success_count} new marks.", "success")
        
        if skipped_pupils:
            flash(f"Skipped {len(skipped_pupils)} pupils (marks already exist for: {', '.join(skipped_pupils)}). Updates are not allowed.", "warning")
            
        if errors:
            flash("Validation issues: " + ", ".join(errors), "danger")

    except Exception as e:
        connection.rollback()
        flash(f"System error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(request.referrer)

    


