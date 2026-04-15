from apps.subject_comments import blueprint
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





@blueprint.route('/subject_comments')
def subject_comments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch subject comments joined with subjects, streams, and users (teachers)
    cursor.execute("""
        SELECT sc.*,
               sub.subject_name,
               st.stream_name,
               CONCAT(u.first_name, ' ', u.last_name, IF(u.other_name IS NOT NULL AND u.other_name != '', CONCAT(' ', u.other_name), '')) AS teacher_name
        FROM subject_comments sc
        LEFT JOIN subjects sub ON sc.subject_id = sub.subject_id
        LEFT JOIN stream st ON sc.stream_id = st.stream_id
        LEFT JOIN users u ON sc.user_id = u.id
        ORDER BY sc.subject_id, sc.min_score
    """)
    subject_comments = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('subject_comments/subject_comments.html',
                           subject_comments=subject_comments,
                           segment='subject_comments')









@blueprint.route('/add_subject_comments', methods=['GET', 'POST'])
def add_subject_comments():
    """Handles adding a new subject comment."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Join subject_assignment with subject, stream, and user for dropdown display
    cursor.execute('''
        SELECT sa.id, s.subject_name, st.stream_name, u.first_name, u.last_name
        FROM subject_assignment sa
        JOIN subjects s ON sa.subject_id = s.subject_id
        JOIN stream st ON sa.stream_id = st.stream_id
        JOIN users u ON sa.user_id = u.id
        ORDER BY s.subject_name, st.stream_name
    ''')
    assignments = [
        {
            "id": row["id"],
            "subject_name": row["subject_name"],
            "stream_name": row["stream_name"],
            "user_name": f"{row['first_name']} {row['last_name']}"
        }
        for row in cursor.fetchall()
    ]

    if request.method == 'POST':
        assignment_id = request.form.get('subject_assignment_id')
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        comment = request.form.get('comment')
        now = datetime.now()

        if not assignment_id or not min_score or not max_score or not comment:
            flash("Please fill out all required fields!", "warning")
        else:
            try:
                # Get subject_id, stream_id, user_id from assignment
                cursor.execute('SELECT subject_id, stream_id, user_id FROM subject_assignment WHERE id = %s', (assignment_id,))
                assignment = cursor.fetchone()
                if not assignment:
                    flash("Selected subject assignment does not exist!", "danger")
                else:
                    subject_id = assignment['subject_id']
                    stream_id = assignment['stream_id']
                    user_id = assignment['user_id']

                    # Check if a comment already exists for the same range in the same subject & stream
                    cursor.execute('''
                        SELECT * FROM subject_comments
                        WHERE subject_id = %s AND stream_id = %s
                        AND min_score = %s AND max_score = %s
                    ''', (subject_id, stream_id, min_score, max_score))
                    existing = cursor.fetchone()

                    if existing:
                        flash("A comment already exists for that score range and subject.", "warning")
                    else:
                        cursor.execute('''
                            INSERT INTO subject_comments (
                                subject_id, stream_id, user_id,
                                min_score, max_score, comment,
                                created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            subject_id, stream_id, user_id,
                            min_score, max_score, comment,
                            now, now
                        ))
                        connection.commit()
                        flash("Subject comment added successfully!", "success")

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'subject_comments/add_subject_comments.html',
        assignments=assignments,
        segment='add_subject_comments'
    )












@blueprint.route('/edit_subject_comments/<int:comment_id>', methods=['GET', 'POST'])
def edit_subject_comments(comment_id):
    """Handles editing an existing subject comment."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch assignments for dropdown
    cursor.execute('''
        SELECT sa.id, s.subject_name, st.stream_name, u.first_name, u.last_name
        FROM subject_assignment sa
        JOIN subjects s ON sa.subject_id = s.subject_id
        JOIN stream st ON sa.stream_id = st.stream_id
        JOIN users u ON sa.user_id = u.id
        ORDER BY s.subject_name, st.stream_name
    ''')
    assignments = [
        {
            "id": row["id"],
            "subject_name": row["subject_name"],
            "stream_name": row["stream_name"],
            "user_name": f"{row['first_name']} {row['last_name']}"
        }
        for row in cursor.fetchall()
    ]

    if request.method == 'POST':
        assignment_id = request.form.get('subject_assignment_id')
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        comment = request.form.get('comment')
        updated_at = datetime.now()

        if not assignment_id or not min_score or not max_score or not comment:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('subject_comments_blueprint.edit_subject_comments', comment_id=comment_id))

        try:
            # Get subject, stream, user from assignment
            cursor.execute("SELECT subject_id, stream_id, user_id FROM subject_assignment WHERE id = %s", (assignment_id,))
            assignment = cursor.fetchone()
            if not assignment:
                flash("Selected assignment not found.", "danger")
                return redirect(url_for('subject_comments_blueprint.edit_subject_comments', comment_id=comment_id))

            subject_id = assignment['subject_id']
            stream_id = assignment['stream_id']
            user_id = assignment['user_id']

            # Check for duplicate
            cursor.execute('''
                SELECT * FROM subject_comments
                WHERE subject_id = %s AND stream_id = %s 
                  AND min_score = %s AND max_score = %s AND comment_id != %s
            ''', (subject_id, stream_id, min_score, max_score, comment_id))
            existing = cursor.fetchone()

            if existing:
                flash("A comment already exists for that score range and subject.", "warning")
                return redirect(url_for('subject_comments_blueprint.edit_subject_comments', comment_id=comment_id))

            # Update subject_comment
            cursor.execute('''
                UPDATE subject_comments
                SET subject_id = %s, stream_id = %s, user_id = %s,
                    min_score = %s, max_score = %s, comment = %s, updated_at = %s
                WHERE comment_id = %s
            ''', (
                subject_id, stream_id, user_id,
                min_score, max_score, comment, updated_at,
                comment_id
            ))
            connection.commit()
            flash("Subject comment updated successfully!", "success")
            return redirect(url_for('subject_comments_blueprint.subject_comments'))

        except mysql.connector.Error as err:
            flash(f"MySQL Error: {err}", "danger")
        finally:
            cursor.close()
            connection.close()

    else:
        # GET method - load the comment
        cursor.execute("SELECT * FROM subject_comments WHERE comment_id = %s", (comment_id,))
        comment_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if not comment_data:
            flash("Subject comment not found.", "danger")
            return redirect(url_for('subject_comments_blueprint.subject_comments'))

        return render_template(
            'subject_comments/edit_subject_comments.html',
            comment=comment_data,
            assignments=assignments,
            segment='subject_comments'
        )










@blueprint.route('/delete_subject_comments/<int:comment_id>', methods=["POST"])
def delete_subject_comments(comment_id):
    """Deletes a subject comment from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Check if comment exists
        cursor.execute("SELECT * FROM subject_comments WHERE comment_id = %s", (comment_id,))
        comment = cursor.fetchone()

        if not comment:
            flash("Subject comment not found.", "warning")
            return redirect(url_for('subject_comments_blueprint.subject_comments'))

        # Proceed with deletion
        cursor.execute("DELETE FROM subject_comments WHERE comment_id = %s", (comment_id,))
        connection.commit()
        flash("Subject comment deleted successfully.", "success")

    except Exception as e:
        flash("An error occurred while deleting the subject comment.", "danger")
        logging.exception("Error deleting subject comment")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('subject_comments_blueprint.subject_comments'))






@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("subject_comments/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'subject_comments'

        return segment

    except:
        return None
