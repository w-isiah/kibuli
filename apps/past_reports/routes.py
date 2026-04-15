from apps.past_reports import blueprint
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
from collections import defaultdict



def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)














@blueprint.route('/scores_positions_past_reports', methods=['GET'])
def scores_positions_past_reports():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Load dropdown data
    cursor.execute("SELECT * FROM classes WHERE class_id IN ('4', '30', '31', '32','33') ORDER BY class_name")
    class_list = cursor.fetchall()

    cursor.execute("SELECT * FROM study_year ORDER BY year_name")
    study_years = cursor.fetchall()

    cursor.execute("SELECT * FROM terms ORDER BY term_name")
    terms = cursor.fetchall()

    cursor.execute("SELECT * FROM assessment ORDER BY assessment_name")
    assessments = cursor.fetchall()

    cursor.execute("SELECT * FROM stream ORDER BY stream_name")
    streams = cursor.fetchall()

    # Read filter values
    class_id = request.args.get('class_id', type=str)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_name = request.args.get('assessment_name', type=str)
    stream_id = request.args.get('stream_id', type=int)

    if not all([class_id, year_id, term_id, assessment_name]):
        cursor.close()
        connection.close()
        return render_template(
            'past_reports/scores_positions_past_reports.html',
            past_reports=[],
            subject_names=[],
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
            segment='past_reports'
        )

    core_subjects = ['MTC', 'ENGLISH', 'SST', 'SCIE']

    # Updated query using s.reg_no and joining via p.pupil_id to enrollment_history
    sql = """
        SELECT 
            p.pupil_id, p.reg_no, p.last_name, p.first_name, p.other_name,
            eh.class_id, eh.stream_id,
            y.year_name, y.year_id,
            t.term_name, t.term_id,
            a.assessment_name,
            sub.subject_name,
            s.Mark,
            g.grade_letter,
            g.weight,
            st.stream_name
        FROM scores s
        JOIN pupils p ON p.reg_no = s.reg_no
        JOIN enrollment_history eh ON eh.pupil_id = p.pupil_id
            AND eh.class_id = %s
            AND eh.year_id = %s
            AND eh.term_id = %s
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN study_year y ON s.year_id = y.year_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        JOIN stream st ON eh.stream_id = st.stream_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        WHERE s.year_id = eh.year_id
          AND s.term_id = eh.term_id
          AND a.assessment_name = %s
    """

    args = [class_id, year_id, term_id, assessment_name]

    if stream_id:
        sql += " AND eh.stream_id = %s"
        args.append(stream_id)

    cursor.execute(sql, args)
    rows = cursor.fetchall()

    if not rows:
        cursor.close()
        connection.close()
        return render_template(
            'past_reports/scores_positions_past_reports.html',
            past_reports=[],
            subject_names=[],
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
            segment='past_reports'
        )

    subject_names = sorted({row['subject_name'] for row in rows})

    # Organize data per pupil
    student_map = {}
    for row in rows:
        pid = row['pupil_id']
        if pid not in student_map:
            fullname = f"{row['last_name']} {row['first_name']} {row['other_name']}".strip()
            student_map[pid] = {
                'reg_no': row['reg_no'],
                'full_name': fullname,
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
        student_map[pid]['marks'][row['subject_name']] = row['Mark']
        student_map[pid]['grades'][row['subject_name']] = row['grade_letter'] or ''
        student_map[pid]['weights'][row['subject_name']] = row['weight'] or 0

    # Compute total/average/aggregate/division
    for student in student_map.values():
        core_marks = [student['marks'].get(sub) for sub in core_subjects]
        filled = [m if m is not None else 0 for m in core_marks]
        total_score = sum(filled)
        avg_score = round(total_score / len(core_subjects), 2)

        if None in core_marks:
            aggregate = 'X'
            division = 'X'
        else:
            aggregate = sum(student['weights'].get(sub, 0) for sub in core_subjects)
            cursor.execute("SELECT division_name FROM division WHERE %s BETWEEN min_score AND max_score LIMIT 1", (aggregate,))
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
    def assign_positions(student_list, key):
        student_list.sort(key=lambda s: (float('inf') if s['aggregate'] == 'X' else -s['average_score'], s['reg_no']))
        prev_score = None
        prev_position = 0
        for idx, student in enumerate(student_list, start=1):
            if student['aggregate'] == 'X':
                student[key] = idx
            else:
                if student['average_score'] != prev_score:
                    prev_position = idx
                student[key] = prev_position
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
        'past_reports/scores_positions_past_reports.html',
        past_reports=students,
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
        segment='past_reports'
    )











@blueprint.route('/scores_positions_past_reports_2', methods=['GET'])
def scores_positions_past_reports_2():
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
            'past_reports/scores_positions_past_reports_2.html',
            past_reports=[],
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
            segment='past_reports'
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
        'past_reports/scores_positions_past_reports_2.html',
        past_reports=students,
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
        segment='past_reports'
    )













@blueprint.route('/scores_positions_past_reports_3', methods=['GET'])
def scores_positions_past_reports_3():
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
            'past_reports/scores_positions_past_reports_3.html',
            past_reports=[],
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
            segment='past_reports'
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
        'past_reports/scores_positions_past_reports_3.html',
        past_reports=students,
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
        segment='past_reports'
    )
