from apps.results_update import blueprint
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





from mysql.connector import Error

@blueprint.route('/results_update', methods=['GET'])
def results_update():
    """Fetches pupil marks per subject for a given assessment, only including those with recorded marks."""

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Dropdown data
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    cursor.execute("SELECT * FROM subjects")
    subjects = cursor.fetchall()

    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    cursor.execute("SELECT * FROM pupils")
    pupils = cursor.fetchall()

    # Filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)
    pupil_name = request.args.get('pupil_name', type=str)
    reg_no = request.args.get('reg_no', type=str)

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'subject_id': subject_id,
        'assessment_name': assessment_name,
        'stream_id': stream_id,
        'pupil_name': pupil_name,
        'reg_no': reg_no
    }

    if not any(filters.values()):
        cursor.close()
        connection.close()
        return render_template(
            'results_update/results_update.html',
            results_update=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            subjects=subjects,
            assessments=assessments,
            streams=streams,
            pupils=pupils,
            selected_class_id=None,
            selected_study_year_id=None,
            selected_term_id=None,
            selected_assessment_name=None,
            selected_subject_id=None,
            selected_stream_id=None,
            selected_pupil_name=None,
            entered_reg_no=None,
            segment='results_update'
        )

    # Query for only pupils with marks
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        p.pupil_id,
        y.year_name,
        str.stream_name,
        s.score_id
    FROM 
        scores s
    INNER JOIN pupils p ON p.reg_no = s.reg_no
    INNER JOIN assessment a ON s.assessment_id = a.assessment_id
    INNER JOIN terms t ON s.term_id = t.term_id
    INNER JOIN subjects sub ON s.subject_id = sub.subject_id
    INNER JOIN study_year y ON s.year_id = y.year_id
    INNER JOIN stream str ON p.stream_id = str.stream_id
    WHERE 1=1
    """

    if class_id:
        query += f" AND p.class_id = {class_id}"
    if stream_id:
        query += f" AND p.stream_id = {stream_id}"
    if year_id:
        query += f" AND y.year_id = {year_id}"
    if term_id:
        query += f" AND t.term_id = {term_id}"
    if subject_id:
        query += f" AND sub.subject_id = {subject_id}"
    if assessment_name:
        query += f" AND a.assessment_name = '{assessment_name}'"
    if pupil_name:
        query += f" AND TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) LIKE '%{pupil_name}%'"
    if reg_no:
        query += f" AND p.reg_no = '{reg_no}'"

    query += " ORDER BY p.last_name, p.first_name, p.other_name"

    cursor.execute(query)
    results_update = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'results_update/results_update.html',
        results_update=results_update,
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
        segment='results_update'
    )










from datetime import datetime
import pytz
from flask import request, session, flash, redirect, url_for

def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

@blueprint.route('/edit_scores', methods=['POST'])
def edit_scores():
    """Edits selected scores, logs changes with reasons."""

    user_id = session.get('id')
    if not user_id:
        flash("You must be logged in to edit scores.", "danger")
        return redirect(url_for('auth.login'))

    # Extract data from form: expected keys like new_marks[score_id], edit_reasons[score_id]
    form_data = request.form.to_dict(flat=False)

    new_marks = {}
    edit_reasons = {}

    for key, values in form_data.items():
        if key.startswith("new_marks[") and key.endswith("]"):
            score_id = key[len("new_marks["):-1]
            new_marks[score_id] = values[0]
        elif key.startswith("edit_reasons[") and key.endswith("]"):
            score_id = key[len("edit_reasons["):-1]
            edit_reasons[score_id] = values[0]

    if not new_marks:
        flash("No marks submitted for editing.", "warning")
        return redirect(request.referrer or url_for('reports_blueprint.reports'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        success_count = 0
        errors = []

        for score_id_str, new_mark_str in new_marks.items():
            reason = edit_reasons.get(score_id_str, "").strip()
            if not reason:
                errors.append(f"Missing reason for score ID {score_id_str}. Skipped.")
                continue

            try:
                score_id = int(score_id_str)
                new_mark = float(new_mark_str)
                if new_mark < 0 or new_mark > 100:
                    errors.append(f"Invalid mark {new_mark} for score ID {score_id}. Skipped.")
                    continue
            except ValueError:
                errors.append(f"Invalid input for score ID {score_id_str}. Skipped.")
                continue

            # Fetch current score record
            cursor.execute("SELECT * FROM scores WHERE score_id = %s", (score_id,))
            row = cursor.fetchone()
            if not row:
                errors.append(f"Score ID {score_id} not found. Skipped.")
                continue

            old_mark = float(row['Mark'])

            if old_mark == new_mark:
                # No change, skip
                continue

            # Update score
            cursor.execute("UPDATE scores SET Mark = %s WHERE score_id = %s", (new_mark, score_id))

            # Insert log entry
            log_query = """
                INSERT INTO score_edit_logs
                (score_id, user_id, class_id, stream_id, term_id, year_id, assessment_id, subject_id, old_mark, new_mark, reason, edited_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            kampala_time = get_kampala_time()

            cursor.execute(log_query, (
                score_id,
                user_id,
                row.get('class_id'),
                row.get('stream_id'),
                row.get('term_id'),
                row.get('year_id'),
                row.get('assessment_id'),
                row.get('subject_id'),
                old_mark,
                new_mark,
                reason,
                kampala_time
            ))

            success_count += 1

        connection.commit()

        if success_count > 0:
            flash(f"Successfully updated {success_count} score(s).", "success")
        if errors:
            flash("Some issues occurred:<br>" + "<br>".join(errors), "warning")

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred: {e}", "danger")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(request.referrer or url_for('reports_blueprint.reports'))








