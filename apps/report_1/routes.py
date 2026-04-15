from collections import defaultdict
from flask import render_template, request
from apps.report_1 import blueprint
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

def get_division(aggregate, division_lookup):
    """Helper to find division based on aggregate score."""
    if aggregate == 'X': return 'X'
    for div in division_lookup:
        if div['min_score'] <= aggregate <= div['max_score']:
            return div['division_name']
    return 'N/A'

@blueprint.route('/report_1', methods=['GET'])
def report_1():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Load Dropdown Metadata
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

    # 2. Capture Filters
    class_id = request.args.get('class_id', type=int)
    stream_id = request.args.get('stream_id', type=int)
    year_id = request.args.get('year_id', type=int)
    term_id = request.args.get('term_id', type=int)
    assessment_names = request.args.getlist('assessment_name')

    if not all([class_id, year_id, term_id, assessment_names]):
        cursor.close()
        conn.close()
        return render_template('report_1/report_1.html', class_list=class_list, study_years=study_years, 
                               terms=terms, assessments=assessments, streams=streams, reports=[], subject_names=[])

    # 3. Fetch Divisions and Teacher
    cursor.execute("SELECT min_score, max_score, division_name FROM division")
    division_lookup = cursor.fetchall()

    cursor.execute("""
        SELECT CONCAT(u.first_name, ' ', u.last_name) AS name 
        FROM classteacher_assignment cta 
        JOIN users u ON u.id = cta.user_id 
        WHERE cta.stream_id = %s AND cta.year_id = %s AND cta.term_id = %s LIMIT 1
    """, (stream_id, year_id, term_id))
    teacher_row = cursor.fetchone()
    class_teacher = teacher_row['name'] if teacher_row else "Not Assigned"

    # 4. Fetch Main Performance Data
    # IMPORTANT: Added t.term_name and sy.year_name to the SELECT
    placeholders = ','.join(['%s'] * len(assessment_names))
    
    # Check your DB: if the names are 'MATHEMATICS', 'ENGLISH', etc., change these strings!
    core_subjects = ['MATH(%)', 'ENGLISH(%)', 'SST', 'SCIE']
    
    query = f"""
        SELECT 
            s.reg_no, p.index_number, p.image,
            CONCAT_WS(' ', p.last_name, p.first_name, p.other_name) AS full_name,
            c.class_name, st.stream_name, st.stream_id,
            t.term_name, sy.year_name, 
            a.assessment_name, sub.subject_name, s.Mark,
            g.grade_letter, g.weight
        FROM scores s
        JOIN pupils p USING (reg_no)
        JOIN classes c ON p.class_id = c.class_id
        JOIN stream st ON p.stream_id = st.stream_id
        JOIN terms t ON s.term_id = t.term_id
        JOIN study_year sy ON s.year_id = sy.year_id
        JOIN assessment a ON s.assessment_id = a.assessment_id
        JOIN subjects sub ON s.subject_id = sub.subject_id
        LEFT JOIN grades g ON s.Mark BETWEEN g.min_score AND g.max_score
        WHERE p.class_id = %s AND s.year_id = %s AND s.term_id = %s
          AND a.assessment_name IN ({placeholders})
    """
    cursor.execute(query, [class_id, year_id, term_id] + assessment_names)
    rows = cursor.fetchall()

    # 5. Data Structuring
    grouped = {}
    subject_stats = defaultdict(lambda: defaultdict(list))
    subject_names = set()

    for row in rows:
        reg = row['reg_no']
        asn = row['assessment_name']
        sub = row['subject_name']
        key = (reg, asn)
        subject_names.add(sub)

        if key not in grouped:
            grouped[key] = {
                **row, 'marks': {}, 'grades': {}, 'weights': {}, 
                'class_teacher': class_teacher
            }
        
        val = int(row['Mark']) if row['Mark'] is not None else None
        grouped[key]['marks'][sub] = val
        grouped[key]['grades'][sub] = row['grade_letter'] or '-'
        grouped[key]['weights'][sub] = row['weight'] or 0
        
        if val is not None:
            subject_stats[asn][sub].append({'reg': reg, 'mark': val})

    # 6. Ranks, Aggregates, Divisions
    final_subject_ranks = defaultdict(lambda: defaultdict(dict))
    for asn, subs in subject_stats.items():
        for sub, entries in subs.items():
            entries.sort(key=lambda x: x['mark'], reverse=True)
            for i, e in enumerate(entries):
                final_subject_ranks[asn][sub][e['reg']] = i + 1

    reports_list = list(grouped.values())
    
    # Sorting is MANDATORY for Jinja's |groupby('reg_no') to work!
    reports_list.sort(key=lambda x: (x['reg_no'], x['assessment_name']))

    for r in reports_list:
        # Debugging: if valid_marks is empty, aggregate will be 'X'
        core_marks = [r['marks'].get(s) for s in core_subjects]
        valid_marks = [m for m in core_marks if m is not None]
        
        if len(valid_marks) < len(core_subjects):
            r['aggregate'], r['division'] = 'X', 'X'
        else:
            r['aggregate'] = sum(r['weights'].get(s, 0) for s in core_subjects)
            r['division'] = get_division(r['aggregate'], division_lookup)
        
        r['average_score'] = round(sum(valid_marks)/len(valid_marks), 1) if valid_marks else 0
        r['subject_ranks'] = {s: final_subject_ranks[r['assessment_name']][s].get(r['reg_no'], '-') for s in subject_names}

    # Positions
    for asn in assessment_names:
        asn_students = [r for r in reports_list if r['assessment_name'] == asn]
        asn_students.sort(key=lambda x: x['average_score'], reverse=True)
        for i, r in enumerate(asn_students): r['class_position'] = i + 1
        
        streams_in_asn = {r['stream_id'] for r in asn_students}
        for s_id in streams_in_asn:
            str_students = [r for r in asn_students if r['stream_id'] == s_id]
            str_students.sort(key=lambda x: x['average_score'], reverse=True)
            for i, r in enumerate(str_students): r['stream_position'] = i + 1

    cursor.close()
    conn.close()

    return render_template('report_1/report_1.html',
        reports=reports_list,
        subject_names=sorted(list(subject_names)),
        class_list=class_list, study_years=study_years,
        terms=terms, assessments=assessments, streams=streams,
        selected_class_id=class_id, selected_stream_id=stream_id,
        selected_study_year_id=year_id, selected_term_id=term_id,
        selected_assessment_name=assessment_names,
        total_class_size=len([r for r in reports_list if r['assessment_name'] == assessment_names[0]]) if reports_list else 0,
        segment='reports'
    )