from apps.reports import blueprint
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





@blueprint.route('/reports', methods=['GET'])
def reports():
    """Fetches pupil marks per subject for a given assessment and renders the reports page,
       including pupils without marks for the chosen assessment."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch dropdown filter data
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

    # Retrieve query parameters
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
            'reports/reports.html',
            reports=[],
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
            segment='reports'
        )

    # Construct the query
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
        pupils p
    LEFT JOIN 
        scores s ON p.reg_no = s.reg_no
    LEFT JOIN 
        assessment a ON s.assessment_id = a.assessment_id
    LEFT JOIN 
        terms t ON s.term_id = t.term_id
    LEFT JOIN 
        subjects sub ON s.subject_id = sub.subject_id
    LEFT JOIN 
        study_year y ON s.year_id = y.year_id
    LEFT JOIN
        stream str ON p.stream_id = str.stream_id
    WHERE 1=1
    """

    if class_id:
        query += f" AND p.class_id = {class_id}"
    if stream_id:
        query += f" AND p.stream_id = {stream_id}"
    if year_id:
        query += f" AND (y.year_id = {year_id} OR y.year_id IS NULL)"
    if term_id:
        query += f" AND (t.term_id = {term_id} OR t.term_id IS NULL)"
    if subject_id:
        query += f" AND (sub.subject_id = {subject_id} OR sub.subject_id IS NULL)"
    if assessment_name:
        query += f" AND (a.assessment_name = '{assessment_name}' OR a.assessment_name IS NULL)"
    if pupil_name:
        query += f" AND TRIM(CONCAT(p.first_name, ' ', COALESCE(p.other_name, ''), ' ', p.last_name)) LIKE '%{pupil_name}%'"
    if reg_no:
        query += f" AND p.reg_no = '{reg_no}'"

    query += " ORDER BY p.last_name, p.first_name, p.other_name"

    cursor.execute(query)
    reports = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'reports/reports.html',
        reports=reports,
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
        segment='reports'
    )











from datetime import datetime
import pytz


def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)

@blueprint.route('/delete_scores', methods=['POST'])
def delete_scores():
    """Deletes selected scores and logs them with optional notes."""

    score_ids = request.form.getlist('score_ids')
    print(score_ids)


    deletion_notes = request.form.get('deletion_notes', '').strip()  # get notes from form (optional)

    if not score_ids:
        flash('No scores selected for deletion.', 'warning')
        return redirect(url_for('reports_blueprint.reports'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch rows to log
        format_strings = ','.join(['%s'] * len(score_ids))
        cursor.execute(f"SELECT * FROM scores WHERE score_id IN ({format_strings})", score_ids)
        rows_to_log = cursor.fetchall()

        # Prepare insert query for logs (includes notes and deleted_at)
        log_query = """
            INSERT INTO scores_del_logs
            (score_id, user_id, reg_no, class_id, stream_id, term_id, year_id, assessment_id, subject_id, Mark, notes, deleted_at)
            VALUES (%(score_id)s, %(user_id)s, %(reg_no)s, %(class_id)s, %(stream_id)s, %(term_id)s, %(year_id)s,
                    %(assessment_id)s, %(subject_id)s, %(Mark)s, %(notes)s, %(deleted_at)s)
        """

        kampala_time = get_kampala_time()

        # Insert each deleted row into the logs table with your deletion notes
        for row in rows_to_log:
            row['deleted_at'] = kampala_time
            # Use deletion notes from form; if none provided, fallback to existing notes or NULL
            row['notes'] = deletion_notes if deletion_notes else row.get('notes', None)
            cursor.execute(log_query, row)

        # Now delete from scores table
        cursor.execute(f"DELETE FROM scores WHERE score_id IN ({format_strings})", score_ids)

        connection.commit()

        flash(f"{cursor.rowcount} score(s) deleted and logged successfully.", 'success')

    except Error as e:
        flash(f"An error occurred: {e}", 'danger')

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for('reports_blueprint.reports'))














@blueprint.route('/report_card/<string:reg_no>', methods=['GET'])
def report_card(reg_no):
    """Generates a detailed report card for a pupil grouped by assessments."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT 
            p.reg_no,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            a.assessment_name,
            s.math,
            s.english,
            s.science,
            s.social_studies,
            s.re,
            s.computer
        FROM 
            scores s
        JOIN 
            pupils p ON s.reg_no = p.reg_no
        JOIN 
            assessment a ON s.assessment_id = a.assessment_id
        WHERE 
            p.reg_no = %s
        ORDER BY 
            a.assessment_id
    """
    cursor.execute(query, (reg_no,))
    records = cursor.fetchall()
    cursor.close()
    connection.close()

    if not records:
        return "No report card found for this pupil.", 404

    pupil_name = records[0]['full_name']
    assessments = []  # Will hold structured per-assessment info
    overall_total = 0
    overall_count = 0

    for row in records:
        subjects = {
            'Math': row['math'],
            'English': row['english'],
            'Science': row['science'],
            'Social Studies': row['social_studies'],
            'RE': row['re'],
            'Computer': row['computer']
        }
        assessment_total = sum(score for score in subjects.values() if score is not None)
        assessment_count = sum(1 for score in subjects.values() if score is not None)

        assessments.append({
            'name': row['assessment_name'],
            'scores': subjects,
            'total': assessment_total,
            'average': round(assessment_total / assessment_count, 2) if assessment_count else 0
        })

        overall_total += assessment_total
        overall_count += assessment_count

    overall_average = round(overall_total / overall_count, 2) if overall_count else 0

    return render_template(
        'reports/report_card.html',
        student_name=pupil_name,
        assessments=assessments,
        overall_total=overall_total,
        overall_average=overall_average
    )












@blueprint.route('/term_reports', methods=['GET'])
def term_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch dropdowns
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'assessment_name': assessment_name
    }

    if not any(filters.values()):
        return render_template(
            'reports/term_reports.html',
            reports=[],
            subject_names=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            subjects=[],  # Empty since we’re filtering
            assessments=assessments,
            selected_class_id=None,
            selected_study_year_id=None,
            selected_term_id=None,
            selected_assessment_name=None,
            segment='reports'
        )

    # Main query to fetch data with grades
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        g.grade_letter,
        g.remark,
        p.pupil_id,
        y.year_name
    FROM 
        scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
    WHERE 1=1
    """

    params = []
    if class_id:
        query += " AND p.class_id = %s"
        params.append(class_id)
    if year_id:
        query += " AND p.year_id = %s"
        params.append(year_id)
    if term_id:
        query += " AND s.term_id = %s"
        params.append(term_id)
    if assessment_name:
        query += " AND a.assessment_name = %s"
        params.append(assessment_name)

    cursor.execute(query, params)
    raw_data = cursor.fetchall()

    # Identify only used subjects
    subject_names = sorted(set(row['subject_name'] for row in raw_data))

    # Pivot logic
    pivoted = {}
    for row in raw_data:
        key = row['reg_no']
        if key not in pivoted:
            pivoted[key] = {
                'reg_no': row['reg_no'],
                'full_name': row['full_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'year_name': row['year_name'],
                'marks': {sub: '' for sub in subject_names},
                'grades': {sub: '' for sub in subject_names},
                'remarks': {sub: '' for sub in subject_names}
            }
        pivoted[key]['marks'][row['subject_name']] = row['Mark']
        pivoted[key]['grades'][row['subject_name']] = row['grade_letter']
        pivoted[key]['remarks'][row['subject_name']] = row['remark']

    reports = list(pivoted.values())

    cursor.close()
    connection.close()

    return render_template(
        'reports/term_reports.html',
        reports=reports,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        subjects=[],  # not needed for table display
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )








@blueprint.route('/scores_reports', methods=['GET'])
def scores_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdowns
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'assessment_name': assessment_name
    }

    if not any(filters.values()):
        return render_template('reports/scores_reports.html',
            reports=[], subject_names=[], class_list=class_list,
            study_years=study_years, terms=terms, assessments=assessments,
            selected_class_id=None, selected_study_year_id=None,
            selected_term_id=None, selected_assessment_name=None, segment='reports'
        )

    # Query with filters
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
        y.year_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        g.grade_letter,
        g.remark
    FROM scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
    WHERE 1=1
    """
    params = []
    if class_id:
        query += " AND p.class_id = %s"
        params.append(class_id)
    if year_id:
        query += " AND p.year_id = %s"
        params.append(year_id)
    if term_id:
        query += " AND s.term_id = %s"
        params.append(term_id)
    if assessment_name:
        query += " AND a.assessment_name = %s"
        params.append(assessment_name)

    cursor.execute(query, params)
    raw_data = cursor.fetchall()
    cursor.close()
    connection.close()

    # Process and pivot using NumPy
    subject_names = sorted({row['subject_name'] for row in raw_data})
    student_map = {}

    for row in raw_data:
        reg = row['reg_no']
        if reg not in student_map:
            student_map[reg] = {
                'reg_no': reg,
                'full_name': row['full_name'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'remarks': {}
            }
        subject = row['subject_name']
        mark = row['Mark']

        student_map[reg]['marks'][subject] = mark if mark is not None else np.nan
        student_map[reg]['grades'][subject] = row['grade_letter'] or ''
        student_map[reg]['remarks'][subject] = row['remark'] or ''

    # Calculate total and average using NumPy
    reports = []
    for student in student_map.values():
        marks_array = np.array([
            student['marks'].get(subject, np.nan) for subject in subject_names
        ], dtype=np.float64)

        total = np.nansum(marks_array)
        count = np.count_nonzero(~np.isnan(marks_array))
        avg = np.round(total / count, 2) if count > 0 else 0

        student['total_score'] = total
        student['average_score'] = avg
        reports.append(student)

    return render_template('reports/scores_reports.html',
        reports=reports, subject_names=subject_names,
        class_list=class_list, study_years=study_years,
        terms=terms, assessments=assessments,
        selected_class_id=class_id, selected_study_year_id=year_id,
        selected_term_id=term_id, selected_assessment_name=assessment_name,
        segment='reports'
    )
















  

@blueprint.route('/scores_positions_reports_remarks', methods=['GET'])
def scores_positions_reports_remarks():  
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown options
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filter parameters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)

    if not all([class_id, year_id, term_id, assessment_name]):
        return render_template('reports/scores_positions_reports_remarks.html',
            reports=[], subject_names=[], class_list=class_list,
            study_years=study_years, terms=terms, assessments=assessments,
            selected_class_id=class_id, selected_study_year_id=year_id,
            selected_term_id=term_id, selected_assessment_name=assessment_name,
            segment='reports'
        )

    # Fetch all scores and grading info
    cursor.execute("""
        SELECT 
            p.reg_no, p.stream_id, p.class_id,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            y.year_name, y.year_id,
            t.term_name, t.term_id,
            a.assessment_name,
            sub.subject_name,
            s.Mark,
            g.grade_letter,
            g.remark,
            g.weight
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s AND a.assessment_name = %s
    """, (class_id, year_id, term_id, assessment_name))
    rows = cursor.fetchall()

    subject_names = sorted({row['subject_name'] for row in rows})

    # Organize by student
    student_map = {}
    for row in rows:
        reg_no = row['reg_no']
        if reg_no not in student_map:
            student_map[reg_no] = {
                'reg_no': reg_no,
                'full_name': row['full_name'],
                'class_id': row['class_id'],
                'stream_id': row['stream_id'],
                'year_id': row['year_id'],
                'term_id': row['term_id'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'remarks': {},
                'weights': {}
            }
        student_map[reg_no]['marks'][row['subject_name']] = row['Mark'] if row['Mark'] is not None else float('nan')
        student_map[reg_no]['grades'][row['subject_name']] = row['grade_letter'] or ''
        student_map[reg_no]['remarks'][row['subject_name']] = row['remark'] or ''
        student_map[reg_no]['weights'][row['subject_name']] = row['weight'] or 0

    # Compute totals, averages, aggregates, and lookup division
    reports = []
    for student in student_map.values():
        marks = np.array([student['marks'].get(sub, float('nan')) for sub in subject_names], dtype=np.float64)
        weights = [student['weights'].get(sub, 0) for sub in subject_names]

        total_score = np.nansum(marks)
        count = np.count_nonzero(~np.isnan(marks))
        average_score = round(total_score / count, 2) if count else 0
        aggregate = sum(weights)

        # Look up division based on aggregate
        cursor.execute("""
            SELECT division_name FROM division
            WHERE %s BETWEEN min_score AND max_score
            LIMIT 1
        """, (aggregate,))
        division_row = cursor.fetchone()
        division_name = division_row['division_name'] if division_row else 'N/A'

        student['total_score'] = total_score
        student['average_score'] = average_score
        student['aggregate'] = aggregate
        student['division'] = division_name
        reports.append(student)

    # Rank students by average (stream and class)
    for student in reports:
        reg_no = student['reg_no']
        stream_id = student['stream_id']
        class_id = student['class_id']
        term_id = student['term_id']
        year_id = student['year_id']

        # Stream position based on average
        cursor.execute("""
            SELECT p.reg_no, AVG(s.Mark) AS avg
            FROM scores s
            JOIN pupils p ON s.reg_no = p.reg_no
            WHERE p.stream_id = %s AND s.term_id = %s AND s.year_id = %s
            GROUP BY p.reg_no ORDER BY avg DESC
        """, (stream_id, term_id, year_id))
        stream_ranks = cursor.fetchall()
        student['stream_position'] = next((i + 1 for i, r in enumerate(stream_ranks) if r['reg_no'] == reg_no), None)

        # Class position based on average
        cursor.execute("""
            SELECT p.reg_no, AVG(s.Mark) AS avg
            FROM scores s
            JOIN pupils p ON s.reg_no = p.reg_no
            WHERE p.class_id = %s AND s.term_id = %s AND s.year_id = %s
            GROUP BY p.reg_no ORDER BY avg DESC
        """, (class_id, term_id, year_id))
        class_ranks = cursor.fetchall()
        student['class_position'] = next((i + 1 for i, r in enumerate(class_ranks) if r['reg_no'] == reg_no), None)

    cursor.close()
    connection.close()

    return render_template('reports/scores_positions_reports_remarks.html',
        reports=reports,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )















@blueprint.route('/assessment_report', methods=['GET'])
def assessment_report():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filters from request
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name')  # NEW

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'assessment_name': assessment_name
    }

    # If no filters selected, render empty page
    if not any(filters.values()):
        return render_template('reports/assessment_report.html',
            reports=[], pivoted_columns=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            assessments=assessments,
            selected_class_id=None,
            selected_study_year_id=None,
            selected_term_id=None,
            selected_assessment_name=None,
            segment='reports'
        )

    # Query with filters
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
        y.year_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark
    FROM scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    WHERE 1=1
    """

    params = []
    if class_id:
        query += " AND p.class_id = %s"
        params.append(class_id)
    if year_id:
        query += " AND s.year_id = %s"
        params.append(year_id)
    if term_id:
        query += " AND s.term_id = %s"
        params.append(term_id)
    if assessment_name:
        query += " AND a.assessment_name = %s"
        params.append(assessment_name)

    cursor.execute(query, params)
    raw_data = cursor.fetchall()
    cursor.close()
    connection.close()

    # Pivot and structure data
    subject_names = sorted({row['subject_name'] for row in raw_data})
    assessment_names = sorted({row['assessment_name'] for row in raw_data})
    pivoted_columns = sorted({f"{subject} ({assessment})" for subject in subject_names for assessment in assessment_names})

    student_map = {}
    for row in raw_data:
        reg = row['reg_no']
        if reg not in student_map:
            student_map[reg] = {
                'reg_no': reg,
                'full_name': row['full_name'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'marks': {}
            }

        key = f"{row['subject_name']} ({row['assessment_name']})"
        student_map[reg]['marks'][key] = row['Mark']

    # Final formatting
    reports = []
    for student in student_map.values():
        total = 0
        count = 0
        for col in pivoted_columns:
            mark = student['marks'].get(col)
            if mark is not None:
                total += mark
                count += 1
        student['total_score'] = total
        student['average_score'] = round(total / count, 2) if count else 0
        reports.append(student)

    # Sort and rank
    reports.sort(key=lambda x: x['average_score'], reverse=True)
    current_rank = 1
    last_avg = None
    for index, student in enumerate(reports):
        if student['average_score'] == last_avg:
            student['position'] = current_rank
        else:
            current_rank = index + 1
            student['position'] = current_rank
            last_avg = student['average_score']

    return render_template('reports/assessment_report.html',
        reports=reports,
        pivoted_columns=pivoted_columns,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )















@blueprint.route('/term_report_card/<string:reg_no>', methods=['GET'])
def term_report_card(reg_no):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch pupil details
    cursor.execute("""
        SELECT p.reg_no, CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
               p.image, p.gender, p.dorm_id, p.stream_id, p.year_id, p.term_id,
               y.year_name, t.term_name, s.stream_name, c.class_name, c.class_id
        FROM pupils p
        JOIN stream s ON p.stream_id = s.stream_id
        JOIN classes c ON s.class_id = c.class_id
        JOIN study_year y ON p.year_id = y.year_id
        JOIN terms t ON p.term_id = t.term_id
        WHERE p.reg_no = %s
    """, (reg_no,))
    pupil = cursor.fetchone()
    if not pupil:
        return "Pupil not found", 404

    # Load grade scale
    cursor.execute("SELECT * FROM grades ORDER BY weight")
    grade_scale = cursor.fetchall()

    def get_grade(score):
        for g in grade_scale:
            if g['min_score'] <= score <= g['max_score']:
                return g['grade_letter'], g['remark']
        return '-', '-'

    # Get all scores
    cursor.execute("""
        SELECT a.assessment_name, sub.subject_name, s.Mark
        FROM scores s
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        WHERE s.reg_no = %s
        ORDER BY sub.subject_name, a.assessment_id
    """, (reg_no,))
    results = cursor.fetchall()

    # Process assessment data
    subject_scores = {}
    assessment_names = set()

    for row in results:
        subject = row['subject_name']
        assess = row['assessment_name']
        mark = float(row['Mark']) if row['Mark'] is not None else None
        assessment_names.add(assess)

        if subject not in subject_scores:
            subject_scores[subject] = {}
        subject_scores[subject][assess] = mark

    assessment_list = sorted(assessment_names)

    subjects_data = []
    overall_total = 0
    subject_count = 0

    for subject, scores in subject_scores.items():
        total = sum([m for m in scores.values() if m is not None])
        count = sum([1 for m in scores.values() if m is not None])
        average = round(total / count, 2) if count else 0
        grade_letter, remark = get_grade(average)
        subject_entry = {
            'subject': subject,
            'marks': [],
            'total': total,
            'average': average,
            'grade': grade_letter,
            'remark': remark
        }

        for assessment in assessment_list:
            mark = scores.get(assessment)
            if mark is not None:
                g, r = get_grade(mark)
                subject_entry['marks'].append({'mark': mark, 'grade': g, 'remark': r})
            else:
                subject_entry['marks'].append({'mark': '-', 'grade': '-', 'remark': '-'})
        
        subjects_data.append(subject_entry)
        overall_total += average
        subject_count += 1

    overall_average = round(overall_total / subject_count, 2) if subject_count else 0
    overall_grade, overall_remark = get_grade(overall_average)

    # Stream and class position
    cursor.execute("""
        SELECT p.reg_no, AVG(s.Mark) AS avg
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        WHERE p.stream_id = %s AND p.term_id = %s AND p.year_id = %s
        GROUP BY p.reg_no ORDER BY avg DESC
    """, (pupil['stream_id'], pupil['term_id'], pupil['year_id']))
    stream_position = next((i+1 for i, r in enumerate(cursor.fetchall()) if r['reg_no'] == reg_no), None)

    cursor.execute("""
        SELECT p.reg_no, AVG(s.Mark) AS avg
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        JOIN stream strm ON p.stream_id = strm.stream_id
        WHERE strm.class_id = %s AND p.term_id = %s AND p.year_id = %s
        GROUP BY p.reg_no ORDER BY avg DESC
    """, (pupil['class_id'], pupil['term_id'], pupil['year_id']))
    class_position = next((i+1 for i, r in enumerate(cursor.fetchall()) if r['reg_no'] == reg_no), None)

    cursor.close()
    connection.close()

    return render_template("reports/term_report_card.html",
        pupil=pupil,
        subjects=subjects_data,
        assessments=assessment_list,
        overall_average=overall_average,
        overall_grade=overall_grade,
        overall_remark=overall_remark,
        stream_position=stream_position,
        class_position=class_position,
        print_date=datetime.now()
    )











@blueprint.route('/scores_p_reports', methods=['GET'])
def scores_p_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    # Get filters from request
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)

    filters = {
        'class_id': class_id,
        'year_id': year_id,
        'term_id': term_id,
        'assessment_name': assessment_name
    }

    # If no filters selected, render empty page
    if not any(filters.values()):
        return render_template('reports/scores_p_reports.html',
            reports=[], subject_names=[], class_list=class_list,
            study_years=study_years, terms=terms, assessments=assessments,
            selected_class_id=None, selected_study_year_id=None,
            selected_term_id=None, selected_assessment_name=None, segment='reports'
        )

    # Build base SQL query
    query = """
    SELECT 
        p.reg_no,
        CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
        y.year_name,
        t.term_name,
        a.assessment_name,
        sub.subject_name,
        s.Mark,
        g.grade_letter,
        g.remark
    FROM scores s
    JOIN pupils p ON s.reg_no = p.reg_no
    JOIN assessment a ON s.assessment_id = a.assessment_id
    JOIN terms t ON s.term_id = t.term_id
    JOIN subjects sub ON s.subject_id = sub.subject_id
    JOIN study_year y ON s.year_id = y.year_id
    LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
    WHERE 1=1
    """

    params = []
    if class_id:
        query += " AND p.class_id = %s"
        params.append(class_id)
    if year_id:
        query += " AND p.year_id = %s"
        params.append(year_id)
    if term_id:
        query += " AND s.term_id = %s"
        params.append(term_id)
    if assessment_name:
        query += " AND a.assessment_name = %s"
        params.append(assessment_name)

    # Execute query
    cursor.execute(query, params)
    raw_data = cursor.fetchall()
    cursor.close()
    connection.close()

    # Extract subject names and initialize student mapping
    subject_names = sorted({row['subject_name'] for row in raw_data})
    student_map = {}

    for row in raw_data:
        reg = row['reg_no']
        if reg not in student_map:
            student_map[reg] = {
                'reg_no': reg,
                'full_name': row['full_name'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'remarks': {}
            }

        subject = row['subject_name']
        mark = row['Mark']

        student_map[reg]['marks'][subject] = mark if mark is not None else np.nan
        student_map[reg]['grades'][subject] = row['grade_letter'] or ''
        student_map[reg]['remarks'][subject] = row['remark'] or ''

    # Calculate totals, averages, and prepare for ranking
    reports = []
    for student in student_map.values():
        marks_array = np.array([
            student['marks'].get(subject, np.nan) for subject in subject_names
        ], dtype=np.float64)

        total = np.nansum(marks_array)
        count = np.count_nonzero(~np.isnan(marks_array))
        average = np.round(total / count, 2) if count > 0 else 0

        student['total_score'] = total
        student['average_score'] = average
        reports.append(student)

    # Sort and assign positions
    reports.sort(key=lambda x: x['average_score'], reverse=True)

    current_position = 1
    last_average = None
    for index, student in enumerate(reports):
        if student['average_score'] == last_average:
            student['position'] = current_position  # same position for tie
        else:
            current_position = index + 1
            student['position'] = current_position
            last_average = student['average_score']

    # Render template with results
    return render_template('reports/scores_p_reports.html',
        reports=reports,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        segment='reports'
    )




















@blueprint.route('/scores_positions_reports', methods=['GET'])
def scores_positions_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes WHERE class_id IN (4, 30, 31, 32,33)")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # Read filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)

    if not all([class_id, year_id, term_id, assessment_name]):
        cursor.close()
        connection.close()
        return render_template(
            'reports/scores_positions_reports.html',
            reports=[],
            subject_names=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            assessments=assessments,
            streams=streams,
            selected_stream_id=stream_id,
            selected_class_id=class_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name,
            segment='reports'
        )

    core_subjects = ['MTC', 'ENGLISH', 'SST', 'SCIE']

    # Fetch scores and related data
    sql = """
        SELECT 
            p.reg_no, p.stream_id, p.class_id,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            y.year_name, y.year_id,
            t.term_name, t.term_id,
            a.assessment_name,
            sub.subject_name,
            s.Mark,
            g.grade_letter,
            g.weight,
            st.stream_name
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        JOIN stream st ON p.stream_id = st.stream_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s AND a.assessment_name = %s
    """
    args = [class_id, year_id, term_id, assessment_name]

    if stream_id:
        sql += " AND p.stream_id = %s"
        args.append(stream_id)

    cursor.execute(sql, args)
    rows = cursor.fetchall()

    subject_names = sorted({row['subject_name'] for row in rows})

    # Build student data map
    student_map = {}
    for row in rows:
        reg_no = row['reg_no']
        if reg_no not in student_map:
            student_map[reg_no] = {
                'reg_no': reg_no,
                'full_name': row['full_name'],
                'class_id': row['class_id'],
                'stream_id': row['stream_id'],
                'stream_name': row['stream_name'],
                'year_id': row['year_id'],
                'term_id': row['term_id'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'weights': {}
            }
        student_map[reg_no]['marks'][row['subject_name']] = row['Mark']
        student_map[reg_no]['grades'][row['subject_name']] = row['grade_letter'] or ''
        student_map[reg_no]['weights'][row['subject_name']] = row['weight'] or 0

    # Calculate totals, averages, aggregate, division
    for student in student_map.values():
        core_marks = [student['marks'].get(sub) for sub in core_subjects]

        # Replace missing marks with zero for total and average calculation
        marks_values = [m if m is not None else 0 for m in core_marks]
        total_score = sum(marks_values)

        # Average is always divided by total number of core subjects (4)
        avg_score = round(total_score / len(core_subjects), 2)

        incomplete = any(m is None for m in core_marks)
        if incomplete:
            aggregate = 'X'
            division = 'X'
        else:
            aggregate = sum(student['weights'].get(sub, 0) for sub in core_subjects)
            cursor.execute("""
                SELECT division_name FROM division
                WHERE %s BETWEEN min_score AND max_score LIMIT 1
            """, (aggregate,))
            div_row = cursor.fetchone()
            division = div_row['division_name'] if div_row else 'N/A'

        student.update({
            'total_score': total_score,
            'average_score': avg_score,
            'aggregate': aggregate,
            'division': division
        })

    students = list(student_map.values())

    def assign_positions(student_list, pos_key):
        # Sort students: aggregate 'X' last, others by descending average_score
        student_list.sort(key=lambda s: (float('inf') if s['aggregate'] == 'X' else -s['average_score'], s['reg_no']))
        prev_score = None
        prev_position = 0
        for idx, student in enumerate(student_list, start=1):
            # Assign numeric position regardless of 'X' aggregate
            if student['aggregate'] == 'X':
                student[pos_key] = idx
            else:
                if student['average_score'] != prev_score:
                    prev_position = idx
                student[pos_key] = prev_position
                prev_score = student['average_score']

    # Assign class positions
    assign_positions(students, 'class_position')

    # Assign stream positions
    from collections import defaultdict
    stream_groups = defaultdict(list)
    for student in students:
        stream_groups[student['stream_id']].append(student)

    for group in stream_groups.values():
        assign_positions(group, 'stream_position')

    cursor.close()
    connection.close()

    return render_template(
        'reports/scores_positions_reports.html',
        reports=students,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        streams=streams,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_stream_id=stream_id,
        segment='reports'
    )

















from collections import defaultdict


@blueprint.route('/vd_reports', methods=['GET'])
def vd_reports():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes WHERE class_id IN (4, 30, 31, 32)")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # Get filters from query parameters
    class_id = request.args.get('class_id', type=int)
    stream_id = request.args.get('stream_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name_list = request.args.getlist('assessment_name')

    # If filters are incomplete, show blank template
    if not all([class_id, stream_id, year_id, term_id, assessment_name_list]):
        cursor.close()
        conn.close()
        return render_template('reports/vd_reports.html',
            reports=[], subject_names=[],
            class_list=class_list, study_years=study_years,
            terms=terms, assessments=assessments, streams=streams,
            selected_class_id=class_id,
            selected_stream_id=stream_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name_list,
            segment='reports'
        )

    # Get class teacher
    cursor.execute("""
        SELECT CONCAT(u.first_name, ' ', u.last_name) AS teacher_name
        FROM classteacher_assignment cta
        JOIN users u ON cta.user_id = u.id
        WHERE cta.stream_id = %s AND cta.year_id = %s AND cta.term_id = %s
        LIMIT 1
    """, (stream_id, year_id, term_id))
    teacher_row = cursor.fetchone()
    class_teacher = teacher_row['teacher_name'] if teacher_row else 'Not Assigned'

    # Get class performance data
    placeholders = ','.join(['%s'] * len(assessment_name_list))
    core_subjects = ['MTC', 'ENGLISH', 'SST', 'SCIE']

    query = f"""
        SELECT s.reg_no, p.stream_id, p.class_id, p.index_number,
               CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
               p.image, c.class_name, st.stream_name,
               y.year_name, y.year_id, t.term_name, t.term_id,
               a.assessment_name, sub.subject_name, s.Mark,
               g.grade_letter, g.weight,
               class_counts.total_class_size, stream_counts.total_stream_size
        FROM scores s
        JOIN pupils p USING (reg_no)
        JOIN classes c ON p.class_id = c.class_id
        JOIN stream st ON p.stream_id = st.stream_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        JOIN (SELECT class_id, COUNT(*) AS total_class_size FROM pupils GROUP BY class_id) class_counts
            ON class_counts.class_id = p.class_id
        JOIN (SELECT class_id, stream_id, COUNT(*) AS total_stream_size FROM pupils GROUP BY class_id, stream_id) stream_counts
            ON stream_counts.class_id = p.class_id AND stream_counts.stream_id = p.stream_id
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s
          AND a.assessment_name IN ({placeholders})
        ORDER BY p.first_name, p.last_name, p.other_name
    """
    cursor.execute(query, [class_id, year_id, term_id] + assessment_name_list)
    rows = cursor.fetchall()

    # Organize data
    from collections import defaultdict

    grouped = {}
    subject_names = set()
    subject_ranks_data = defaultdict(lambda: defaultdict(list))

    for row in rows:
        key = (row['reg_no'], row['assessment_name'])
        subject_names.add(row['subject_name'])

        # Collect for ranking
        subject_ranks_data[row['assessment_name']][row['subject_name']].append({
            'reg_no': row['reg_no'],
            'Mark': int(row['Mark']) if row['Mark'] is not None else None
        })

        if key not in grouped:
            grouped[key] = {
                'reg_no': row['reg_no'], 'index_number': row['index_number'],
                'full_name': row['full_name'], 'image': row['image'],
                'class_id': row['class_id'], 'stream_id': row['stream_id'],
                'class_name': row['class_name'], 'stream_name': row['stream_name'],
                'year_id': row['year_id'], 'term_id': row['term_id'],
                'year_name': row['year_name'], 'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {}, 'grades': {}, 'weights': {},
                'total_class_size': row['total_class_size'],
                'total_stream_size': row['total_stream_size'],
                'class_teacher': class_teacher  # ✅ Correct key name
            }

        student = grouped[key]
        student['marks'][row['subject_name']] = int(row['Mark']) if row['Mark'] is not None else None
        student['grades'][row['subject_name']] = row['grade_letter'] or ''
        student['weights'][row['subject_name']] = row['weight'] or 0

    # Rank students by subject
    subject_ranks = defaultdict(lambda: defaultdict(dict))
    for assessment, subjects in subject_ranks_data.items():
        for subject, entries in subjects.items():
            entries.sort(key=lambda x: -x['Mark'] if x['Mark'] is not None else float('-inf'))
            prev_mark, prev_rank = None, 0
            for i, entry in enumerate(entries):
                if entry['Mark'] != prev_mark:
                    prev_rank = i + 1
                subject_ranks[assessment][subject][entry['reg_no']] = prev_rank
                prev_mark = entry['Mark']

    # Compute totals, aggregates, divisions
    for student in grouped.values():
        marks = [student['marks'].get(s) for s in core_subjects]
        total_score = sum(m for m in marks if m is not None)
        count = len([m for m in marks if m is not None])
        avg_score = round(total_score / count, 2) if count else 0

        if any(m is None for m in marks):
            division, agg = 'X', 'X'
        else:
            weights = [student['weights'].get(s, 0) for s in core_subjects]
            agg = sum(weights)
            cursor.execute("SELECT division_name FROM division WHERE %s BETWEEN min_score AND max_score LIMIT 1", (agg,))
            div_row = cursor.fetchone()
            division = div_row['division_name'] if div_row else 'N/A'

        ranks = {
            subject: subject_ranks[student['assessment_name']][subject].get(student['reg_no'])
            for subject in subject_names
        }

        student.update({
            'total_score': total_score,
            'average_score': avg_score,
            'aggregate': agg,
            'division': division,
            'subject_ranks': ranks
        })

    # Class positions
    class_group = defaultdict(list)
    for s in grouped.values():
        class_group[s['assessment_name']].append(s)

    for students in class_group.values():
        students.sort(key=lambda s: -s['average_score'] if isinstance(s['average_score'], (int, float)) else float('-inf'))
        prev_score, prev_rank = None, 0
        for i, s in enumerate(students):
            if s['average_score'] != prev_score:
                prev_rank = i + 1
            s['class_position'] = prev_rank
            prev_score = s['average_score']

    # Stream positions
    stream_group = defaultdict(list)
    for s in grouped.values():
        stream_group[s['assessment_name']].append(s)

    for students in stream_group.values():
        stream_map = defaultdict(list)
        for s in students:
            stream_map[s['stream_id']].append(s)
        for sgroup in stream_map.values():
            sgroup.sort(key=lambda s: -s['average_score'] if isinstance(s['average_score'], (int, float)) else float('-inf'))
            prev_score, prev_rank = None, 0
            for i, s in enumerate(sgroup):
                if s['average_score'] != prev_score:
                    prev_rank = i + 1
                s['stream_position'] = prev_rank
                prev_score = s['average_score']

    cursor.close()
    conn.close()

    return render_template('reports/vd_reports.html',
        reports=list(grouped.values()),
        subject_names=sorted(subject_names),
        class_list=class_list, study_years=study_years,
        terms=terms, assessments=assessments, streams=streams,
        selected_class_id=class_id,
        selected_stream_id=stream_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name_list,
        segment='reports'
    )










from collections import defaultdict
from flask import request, render_template

@blueprint.route('/vd_reports_2', methods=['GET'])
def vd_reports_2():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Load dropdown data for filters
    cursor.execute("SELECT * FROM classes WHERE class_id IN (28, 27)")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()

    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # Read filter parameters from request
    class_id = request.args.get('class_id', type=int)
    stream_id = request.args.get('stream_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name_list = request.args.getlist('assessment_name')

    # If any required filter is missing, render page with dropdowns only
    if not all([class_id, stream_id, year_id, term_id, assessment_name_list]):
        cursor.close()
        conn.close()
        return render_template(
            'reports/vd_reports_2.html',
            reports=[],
            subject_names=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            assessments=assessments,
            streams=streams,
            selected_class_id=class_id,
            selected_stream_id=stream_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name_list,
            segment='reports'
        )

    # Get class teacher name for the selected stream, year, and term
    cursor.execute("""
        SELECT CONCAT(u.first_name, ' ', u.last_name) AS teacher_name
        FROM classteacher_assignment cta
        JOIN users u ON cta.user_id = u.id
        WHERE cta.stream_id = %s AND cta.year_id = %s AND cta.term_id = %s
        LIMIT 1
    """, (stream_id, year_id, term_id))
    teacher_row = cursor.fetchone()
    class_teacher = teacher_row['teacher_name'] if teacher_row else 'Not Assigned'

    # Prepare placeholders for SQL IN clause for assessments
    placeholders = ','.join(['%s'] * len(assessment_name_list))

    # Define subjects used for calculations
    total_avg_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B', 'COMPUTER', 'R.E', 'READING', 'LUGANDA'])
    aggregate_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B'])

    # Query to fetch scores and related info for students matching filters
    class_query = f"""
        SELECT s.reg_no, p.stream_id, p.class_id, p.index_number,
               CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
               p.image, c.class_name, st.stream_name,
               y.year_name, y.year_id, t.term_name, t.term_id,
               a.assessment_name, sub.subject_name, s.Mark,
               g.grade_letter, g.weight,
               class_counts.total_class_size, stream_counts.total_stream_size
        FROM scores s
        JOIN pupils p USING (reg_no)
        JOIN classes c ON p.class_id = c.class_id
        JOIN stream st ON p.stream_id = st.stream_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        JOIN (SELECT class_id, COUNT(*) AS total_class_size FROM pupils GROUP BY class_id) class_counts
          ON class_counts.class_id = p.class_id
        JOIN (SELECT class_id, stream_id, COUNT(*) AS total_stream_size FROM pupils GROUP BY class_id, stream_id) stream_counts
          ON stream_counts.class_id = p.class_id AND stream_counts.stream_id = p.stream_id
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s
          AND a.assessment_name IN ({placeholders})
        ORDER BY p.first_name, p.last_name, p.other_name
    """
    class_params = [class_id, year_id, term_id] + assessment_name_list
    cursor.execute(class_query, class_params)
    class_rows = cursor.fetchall()

    # Group data by student and assessment
    class_grouped = {}
    subject_names = set()
    subject_rankings = defaultdict(lambda: defaultdict(list))

    for row in class_rows:
        key = (row['reg_no'], row['assessment_name'])
        subject_names.add(row['subject_name'])

        # Collect marks for ranking calculation
        subject_rankings[row['assessment_name']][row['subject_name']].append({
            'reg_no': row['reg_no'],
            'Mark': int(row['Mark']) if row['Mark'] is not None else None
        })

        if key not in class_grouped:
            class_grouped[key] = {
                'reg_no': row['reg_no'],
                'index_number': row['index_number'],
                'full_name': row['full_name'],
                'image': row['image'],
                'class_id': row['class_id'],
                'stream_id': row['stream_id'],
                'class_name': row['class_name'],
                'stream_name': row['stream_name'],
                'year_id': row['year_id'],
                'term_id': row['term_id'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'weights': {},
                'total_class_size': row['total_class_size'],
                'total_stream_size': row['total_stream_size']
            }

        student = class_grouped[key]
        student['marks'][row['subject_name']] = int(row['Mark']) if row['Mark'] is not None else None
        student['grades'][row['subject_name']] = row['grade_letter'] or ''
        student['weights'][row['subject_name']] = row['weight'] or 0

    # Compute subject ranks per assessment and subject
    subject_ranks = defaultdict(lambda: defaultdict(dict))
    for assessment, subjects in subject_rankings.items():
        for subject, entries in subjects.items():
            # Sort descending by mark (None marks go last)
            entries.sort(key=lambda x: -x['Mark'] if x['Mark'] is not None else float('-inf'))
            prev_mark, prev_rank = None, 0
            for idx, entry in enumerate(entries):
                if entry['Mark'] != prev_mark:
                    prev_rank = idx + 1
                subject_ranks[assessment][subject][entry['reg_no']] = prev_rank
                prev_mark = entry['Mark']

    # Calculate totals, averages, aggregates, divisions, and ranks for each student
    for student in class_grouped.values():
        # Total and average of selected subjects
        total_marks = [student['marks'].get(sub) for sub in total_avg_subjects if student['marks'].get(sub) is not None]
        total_score = sum(total_marks)
        avg_score = round(total_score / len(total_marks), 2) if total_marks else 0

        # Aggregate and division from core subjects
        core_marks = [student['marks'].get(sub) for sub in aggregate_subjects]
        if any(mark is None for mark in core_marks):
            agg = 'X'
            division = 'X'
        else:
            core_weights = [student['weights'].get(sub, 0) for sub in aggregate_subjects]
            agg = sum(core_weights)
            cursor.execute(
                "SELECT division_name FROM division WHERE %s BETWEEN min_score AND max_score LIMIT 1",
                (agg,)
            )
            div_row = cursor.fetchone()
            division = div_row['division_name'] if div_row else 'N/A'

        # Get subject ranks for this student
        ranks = {}
        for subject in subject_names:
            ranks[subject] = subject_ranks[student['assessment_name']][subject].get(student['reg_no'])

        # Update student record
        student.update({
            'total_score': total_score,
            'average_score': avg_score,
            'aggregate': agg,
            'division': division,
            'subject_ranks': ranks
        })

    # Calculate class positions based on average_score
    assessment_groups_class = defaultdict(list)
    for student in class_grouped.values():
        assessment_groups_class[student['assessment_name']].append(student)

    for group in assessment_groups_class.values():
        group.sort(key=lambda x: -x['average_score'] if isinstance(x['average_score'], (int, float)) else float('-inf'))
        prev_score, prev_position = None, 0
        for idx, rpt in enumerate(group):
            if rpt['average_score'] != prev_score:
                prev_position = idx + 1
            rpt['class_position'] = prev_position
            prev_score = rpt['average_score']

    # Calculate stream positions based on average_score within streams
    assessment_groups_stream = defaultdict(list)
    for rpt in class_grouped.values():
        assessment_groups_stream[rpt['assessment_name']].append(rpt)

    for group in assessment_groups_stream.values():
        streams_group = defaultdict(list)
        for rpt in group:
            streams_group[rpt['stream_id']].append(rpt)
        for sgroup in streams_group.values():
            sgroup.sort(key=lambda x: -x['average_score'] if isinstance(x['average_score'], (int, float)) else float('-inf'))
            prev_score, prev_position = None, 0
            for idx, rpt in enumerate(sgroup):
                if rpt['average_score'] != prev_score:
                    prev_position = idx + 1
                rpt['stream_position'] = prev_position
                prev_score = rpt['average_score']

    # Close DB connections
    cursor.close()
    conn.close()

    # Render the template with all data including the class teacher
    return render_template(
        'reports/vd_reports_2.html',
        reports=list(class_grouped.values()),
        subject_names=sorted(subject_names),
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        streams=streams,
        selected_class_id=class_id,
        selected_stream_id=stream_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name_list,
        class_teacher=class_teacher,
        segment='reports'
    )









@blueprint.route('/scores_positions_reports_2', methods=['GET'])
def scores_positions_reports_2():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes WHERE class_id IN (28,27)")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # Read filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)

    if not all([class_id, year_id, term_id, assessment_name]):
        cursor.close()
        connection.close()
        return render_template(
            'reports/scores_positions_reports_2.html',
            reports=[],
            subject_names=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            assessments=assessments,
            streams=streams,
            selected_stream_id=stream_id,
            selected_class_id=class_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name,
            segment='reports'
        )

    # Define subject groups
    total_avg_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B', 'COMPUTER', 'R.E', 'READING','LUGANDA'])  # total & average
    aggregate_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B'])  # aggregate & division

    # Fetch scores
    sql = """
        SELECT 
            p.reg_no, p.stream_id, p.class_id,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            y.year_name, y.year_id,
            t.term_name, t.term_id,
            a.assessment_name,
            sub.subject_name,
            s.Mark,
            g.grade_letter,
            g.weight,
            st.stream_name
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        JOIN stream st ON p.stream_id = st.stream_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s AND a.assessment_name = %s
    """
    args = [class_id, year_id, term_id, assessment_name]

    if stream_id:
        sql += " AND p.stream_id = %s"
        args.append(stream_id)

    cursor.execute(sql, args)
    rows = cursor.fetchall()

    subject_names = sorted({row['subject_name'] for row in rows})

    # Build student map
    student_map = {}
    for row in rows:
        reg_no = row['reg_no']
        if reg_no not in student_map:
            student_map[reg_no] = {
                'reg_no': reg_no,
                'full_name': row['full_name'],
                'class_id': row['class_id'],
                'stream_id': row['stream_id'],
                'stream_name': row['stream_name'],
                'year_id': row['year_id'],
                'term_id': row['term_id'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'weights': {}
            }
        student_map[reg_no]['marks'][row['subject_name']] = row['Mark']
        student_map[reg_no]['grades'][row['subject_name']] = row['grade_letter'] or ''
        student_map[reg_no]['weights'][row['subject_name']] = row['weight'] or 0

    # Calculate totals, averages, aggregate, division
    for student in student_map.values():
        # --- Total & Average ---
        total_marks = [student['marks'].get(sub) for sub in total_avg_subjects if student['marks'].get(sub) is not None]
        total_score = sum(total_marks)
        avg_score = round(total_score / len(total_marks), 2) if total_marks else 0

        # --- Aggregate & Division ---
        core_marks = [student['marks'].get(sub) for sub in aggregate_subjects]
        if any(mark is None for mark in core_marks):
            aggregate = 'X'
            division = 'X'
        else:
            aggregate = sum(student['weights'].get(sub, 0) for sub in aggregate_subjects)
            cursor.execute("""
                SELECT division_name FROM division
                WHERE %s BETWEEN min_score AND max_score LIMIT 1
            """, (aggregate,))
            div_row = cursor.fetchone()
            division = div_row['division_name'] if div_row else 'N/A'

        student.update({
            'total_score': total_score,
            'average_score': avg_score,
            'aggregate': aggregate,
            'division': division
        })

    students = list(student_map.values())

    # Positioning
    def assign_positions(student_list, pos_key):
        student_list.sort(key=lambda s: (float('inf') if s['aggregate'] == 'X' else -s['average_score'], s['reg_no']))
        prev_score, prev_position = None, 0
        for idx, student in enumerate(student_list, start=1):
            if student['aggregate'] == 'X':
                student[pos_key] = idx
            else:
                if student['average_score'] != prev_score:
                    prev_position = idx
                student[pos_key] = prev_position
                prev_score = student['average_score']

    assign_positions(students, 'class_position')

    from collections import defaultdict
    stream_groups = defaultdict(list)
    for student in students:
        stream_groups[student['stream_id']].append(student)

    for group in stream_groups.values():
        assign_positions(group, 'stream_position')

    cursor.close()
    connection.close()

    return render_template(
        'reports/scores_positions_reports_2.html',
        reports=students,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        streams=streams,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_stream_id=stream_id,
        segment='reports'
    )









@blueprint.route('/vd_reports_3', methods=['GET'])
def vd_reports_3():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes WHERE class_id IN (29)")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # Read filters
    class_id = request.args.get('class_id', type=int)
    stream_id = request.args.get('stream_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name_list = request.args.getlist('assessment_name')

    if not all([class_id, stream_id, year_id, term_id, assessment_name_list]):
        cursor.close()
        conn.close()
        return render_template('reports/vd_reports_3.html',
            reports=[], subject_names=[],
            class_list=class_list, study_years=study_years,
            terms=terms, assessments=assessments, streams=streams,
            selected_class_id=class_id,
            selected_stream_id=stream_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name_list,
            segment='reports')

    placeholders = ','.join(['%s'] * len(assessment_name_list))
    # Subjects used for calculation
    total_avg_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B', 'COMPUTER', 'R.E', 'LUGANDA'])  # for total and average
    aggregate_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B'])  # for aggregate and division

    class_query = f"""
        SELECT s.reg_no, p.stream_id, p.class_id, p.index_number,
               CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
               p.image, c.class_name, st.stream_name,
               y.year_name, y.year_id, t.term_name, t.term_id,
               a.assessment_name, sub.subject_name, s.Mark,
               g.grade_letter, g.weight,
               class_counts.total_class_size, stream_counts.total_stream_size
        FROM scores s
        JOIN pupils p USING (reg_no)
        JOIN classes c ON p.class_id = c.class_id
        JOIN stream st ON p.stream_id = st.stream_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        JOIN (SELECT class_id, COUNT(*) AS total_class_size FROM pupils GROUP BY class_id) class_counts
          ON class_counts.class_id = p.class_id
        JOIN (SELECT class_id, stream_id, COUNT(*) AS total_stream_size FROM pupils GROUP BY class_id, stream_id) stream_counts
          ON stream_counts.class_id = p.class_id AND stream_counts.stream_id = p.stream_id
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s
          AND a.assessment_name IN ({placeholders})
        ORDER BY p.first_name, p.last_name, p.other_name
    """
    class_params = [class_id, year_id, term_id] + assessment_name_list
    cursor.execute(class_query, class_params)
    class_rows = cursor.fetchall()

    class_grouped = {}
    subject_names = set()
    subject_rankings = defaultdict(lambda: defaultdict(list))

    for row in class_rows:
        key = (row['reg_no'], row['assessment_name'])
        subject_names.add(row['subject_name'])

        subject_rankings[row['assessment_name']][row['subject_name']].append({
            'reg_no': row['reg_no'],
            'Mark': int(row['Mark']) if row['Mark'] is not None else None
        })

        if key not in class_grouped:
            class_grouped[key] = {
                'reg_no': row['reg_no'], 'index_number': row['index_number'],
                'full_name': row['full_name'], 'image': row['image'],
                'class_id': row['class_id'], 'stream_id': row['stream_id'],
                'class_name': row['class_name'], 'stream_name': row['stream_name'],
                'year_id': row['year_id'], 'term_id': row['term_id'],
                'year_name': row['year_name'], 'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {}, 'grades': {}, 'weights': {},
                'total_class_size': row['total_class_size'],
                'total_stream_size': row['total_stream_size']
            }

        student = class_grouped[key]
        student['marks'][row['subject_name']] = int(row['Mark']) if row['Mark'] is not None else None
        student['grades'][row['subject_name']] = row['grade_letter'] or ''
        student['weights'][row['subject_name']] = row['weight'] or 0

    # Compute subject ranks
    subject_ranks = defaultdict(lambda: defaultdict(dict))
    for assessment, subjects in subject_rankings.items():
        for subject, entries in subjects.items():
            entries.sort(key=lambda x: -x['Mark'] if x['Mark'] is not None else float('-inf'))
            prev_mark, prev_rank = None, 0
            for idx, entry in enumerate(entries):
                if entry['Mark'] != prev_mark:
                    prev_rank = idx + 1
                subject_ranks[assessment][subject][entry['reg_no']] = prev_rank
                prev_mark = entry['Mark']

    for student in class_grouped.values():
        # Total & average from total_avg_subjects
        total_marks = [student['marks'].get(sub) for sub in total_avg_subjects if student['marks'].get(sub) is not None]
        total_score = sum(total_marks)
        avg_score = round(total_score / len(total_marks), 2) if total_marks else 0

        # Aggregate & Division from aggregate_subjects
        core_marks = [student['marks'].get(sub) for sub in aggregate_subjects]
        if any(mark is None for mark in core_marks):
            agg = 'X'
            division = 'X'
        else:
            core_weights = [student['weights'].get(sub, 0) for sub in aggregate_subjects]
            agg = sum(core_weights)
            cursor.execute("SELECT division_name FROM division WHERE %s BETWEEN min_score AND max_score LIMIT 1", (agg,))
            div_row = cursor.fetchone()
            division = div_row['division_name'] if div_row else 'N/A'

        # Subject ranks
        ranks = {}
        for subject in subject_names:
            rank = subject_ranks[student['assessment_name']][subject].get(student['reg_no'])
            ranks[subject] = rank

        student.update({
            'total_score': total_score,
            'average_score': avg_score,
            'aggregate': agg,
            'division': division,
            'subject_ranks': ranks
        })

    # Class positions
    assessment_groups_class = defaultdict(list)
    for student in class_grouped.values():
        assessment_groups_class[student['assessment_name']].append(student)

    for group in assessment_groups_class.values():
        group.sort(key=lambda x: -x['average_score'] if isinstance(x['average_score'], (int, float)) else float('-inf'))
        prev_score, prev_position = None, 0
        for idx, rpt in enumerate(group):
            if rpt['average_score'] != prev_score:
                prev_position = idx + 1
            rpt['class_position'] = prev_position
            prev_score = rpt['average_score']

    # Stream positions
    assessment_groups_stream = defaultdict(list)
    for rpt in class_grouped.values():
        assessment_groups_stream[rpt['assessment_name']].append(rpt)

    for group in assessment_groups_stream.values():
        streams_group = defaultdict(list)
        for rpt in group:
            streams_group[rpt['stream_id']].append(rpt)
        for sgroup in streams_group.values():
            sgroup.sort(key=lambda x: -x['average_score'] if isinstance(x['average_score'], (int, float)) else float('-inf'))
            prev_score, prev_position = None, 0
            for idx, rpt in enumerate(sgroup):
                if rpt['average_score'] != prev_score:
                    prev_position = idx + 1
                rpt['stream_position'] = prev_position
                prev_score = rpt['average_score']

    cursor.close()
    conn.close()

    return render_template('reports/vd_reports_3.html',
        reports=list(class_grouped.values()),
        subject_names=sorted(subject_names),
        class_list=class_list, study_years=study_years,
        terms=terms, assessments=assessments, streams=streams,
        selected_class_id=class_id,
        selected_stream_id=stream_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name_list,
        segment='reports')










@blueprint.route('/scores_positions_reports_3', methods=['GET'])
def scores_positions_reports_3():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes WHERE class_id IN (29)")
    class_list = cursor.fetchall()
    cursor.execute("SELECT * FROM study_year")
    study_years = cursor.fetchall()
    cursor.execute("SELECT * FROM terms")
    terms = cursor.fetchall()
    cursor.execute("SELECT * FROM assessment")
    assessments = cursor.fetchall()
    cursor.execute("SELECT * FROM stream")
    streams = cursor.fetchall()

    # Read filters
    class_id = request.args.get('class_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)

    if not all([class_id, year_id, term_id, assessment_name]):
        cursor.close()
        connection.close()
        return render_template(
            'reports/scores_positions_reports_3.html',
            reports=[],
            subject_names=[],
            class_list=class_list,
            study_years=study_years,
            terms=terms,
            assessments=assessments,
            streams=streams,
            selected_stream_id=stream_id,
            selected_class_id=class_id,
            selected_study_year_id=year_id,
            selected_term_id=term_id,
            selected_assessment_name=assessment_name,
            segment='reports'
        )

    # Define subject groups
    total_avg_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B', 'COMPUTER', 'R.E', 'LUGANDA'])  # total & average
    aggregate_subjects = sorted(['MTC', 'ENGLISH', 'LITERACY 1A', 'LITERACY 1B'])  # aggregate & division

    # Fetch scores
    sql = """
        SELECT 
            p.reg_no, p.stream_id, p.class_id,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            y.year_name, y.year_id,
            t.term_name, t.term_id,
            a.assessment_name,
            sub.subject_name,
            s.Mark,
            g.grade_letter,
            g.weight,
            st.stream_name
        FROM scores s
        JOIN pupils p ON s.reg_no = p.reg_no
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        JOIN stream st ON p.stream_id = st.stream_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s AND a.assessment_name = %s
    """
    args = [class_id, year_id, term_id, assessment_name]

    if stream_id:
        sql += " AND p.stream_id = %s"
        args.append(stream_id)

    cursor.execute(sql, args)
    rows = cursor.fetchall()

    subject_names = sorted({row['subject_name'] for row in rows})

    # Build student map
    student_map = {}
    for row in rows:
        reg_no = row['reg_no']
        if reg_no not in student_map:
            student_map[reg_no] = {
                'reg_no': reg_no,
                'full_name': row['full_name'],
                'class_id': row['class_id'],
                'stream_id': row['stream_id'],
                'stream_name': row['stream_name'],
                'year_id': row['year_id'],
                'term_id': row['term_id'],
                'year_name': row['year_name'],
                'term_name': row['term_name'],
                'assessment_name': row['assessment_name'],
                'marks': {},
                'grades': {},
                'weights': {}
            }
        student_map[reg_no]['marks'][row['subject_name']] = row['Mark']
        student_map[reg_no]['grades'][row['subject_name']] = row['grade_letter'] or ''
        student_map[reg_no]['weights'][row['subject_name']] = row['weight'] or 0

    # Calculate totals, averages, aggregate, division
    for student in student_map.values():
        # --- Total & Average ---
        total_marks = [student['marks'].get(sub) for sub in total_avg_subjects if student['marks'].get(sub) is not None]
        total_score = sum(total_marks)
        avg_score = round(total_score / len(total_marks), 2) if total_marks else 0

        # --- Aggregate & Division ---
        core_marks = [student['marks'].get(sub) for sub in aggregate_subjects]
        if any(mark is None for mark in core_marks):
            aggregate = 'X'
            division = 'X'
        else:
            aggregate = sum(student['weights'].get(sub, 0) for sub in aggregate_subjects)
            cursor.execute("""
                SELECT division_name FROM division
                WHERE %s BETWEEN min_score AND max_score LIMIT 1
            """, (aggregate,))
            div_row = cursor.fetchone()
            division = div_row['division_name'] if div_row else 'N/A'

        student.update({
            'total_score': total_score,
            'average_score': avg_score,
            'aggregate': aggregate,
            'division': division
        })

    students = list(student_map.values())

    # Positioning
    def assign_positions(student_list, pos_key):
        student_list.sort(key=lambda s: (float('inf') if s['aggregate'] == 'X' else -s['average_score'], s['reg_no']))
        prev_score, prev_position = None, 0
        for idx, student in enumerate(student_list, start=1):
            if student['aggregate'] == 'X':
                student[pos_key] = idx
            else:
                if student['average_score'] != prev_score:
                    prev_position = idx
                student[pos_key] = prev_position
                prev_score = student['average_score']

    assign_positions(students, 'class_position')

    from collections import defaultdict
    stream_groups = defaultdict(list)
    for student in students:
        stream_groups[student['stream_id']].append(student)

    for group in stream_groups.values():
        assign_positions(group, 'stream_position')

    cursor.close()
    connection.close()

    return render_template(
        'reports/scores_positions_reports_3.html',
        reports=students,
        subject_names=subject_names,
        class_list=class_list,
        study_years=study_years,
        terms=terms,
        assessments=assessments,
        streams=streams,
        selected_class_id=class_id,
        selected_study_year_id=year_id,
        selected_term_id=term_id,
        selected_assessment_name=assessment_name,
        selected_stream_id=stream_id,
        segment='reports'
    )
