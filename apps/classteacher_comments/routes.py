from apps.classteacher_comments import blueprint
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





@blueprint.route('/classteacher_comments')
def classteacher_comments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            ctc.comment_id,
            ctc.min_score,
            ctc.max_score,
            ctc.comment,
            ctc.created_at,
            ctc.updated_at,

            -- Teacher info
            u.id AS teacher_id,
            CONCAT(u.first_name, ' ', u.last_name,
                IF(u.other_name IS NOT NULL AND u.other_name != '', CONCAT(' ', u.other_name), '')
            ) AS teacher_name,

            -- Stream info
            s.stream_id,
            s.stream_name

        FROM classteacher_comments ctc
        LEFT JOIN users u ON ctc.user_id = u.id
        LEFT JOIN stream s ON ctc.stream_id = s.stream_id
        LEFT JOIN classteacher_assignment cta 
            ON cta.user_id = ctc.user_id AND cta.stream_id = ctc.stream_id

        ORDER BY ctc.min_score ASC
    """)

    comments = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template(
        'classteacher_comments/class_teacher_comments.html',
        classteacher_comments=comments,
        segment='classteacher_comments'
    )










@blueprint.route('/add_classteacher_comments', methods=['GET', 'POST'])
def add_classteacher_comments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    logged_in_user_id = session.get('id')
    if not logged_in_user_id:
        flash("You must be logged in to add a comment.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    # Fetch streams for dropdown
    cursor.execute("SELECT stream_id, stream_name FROM stream ORDER BY stream_name")
    streams = cursor.fetchall()

    # Fetch teacher user_ids assigned to the logged-in user (assuming one or more)
    # Adjust the WHERE clause if needed based on your business logic
    cursor.execute("""
        SELECT DISTINCT user_id 
        FROM classteacher_assignment 
        WHERE user_id = %s
    """, (logged_in_user_id,))
    assigned_teachers = cursor.fetchall()
    # If no assigned teachers found, use logged_in_user_id by default
    if assigned_teachers:
        teacher_user_ids = [t['user_id'] for t in assigned_teachers]
    else:
        teacher_user_ids = [logged_in_user_id]

    if request.method == 'POST':
        # Get form values
        stream_id = request.form.get('stream_id')
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        comment = request.form.get('comment')
        now = datetime.now()

        # Validate input
        if not stream_id or not min_score or not max_score or not comment:
            flash("Please fill in all required fields.", "warning")
        else:
            try:
                # For simplicity, assuming one teacher_user_id; if multiple, pick the first or adjust logic
                teacher_user_id = teacher_user_ids[0]

                # Check if similar comment exists for this teacher and stream & score range
                cursor.execute("""
                    SELECT * FROM classteacher_comments 
                    WHERE user_id = %s AND stream_id = %s AND min_score = %s AND max_score = %s
                """, (teacher_user_id, stream_id, min_score, max_score))
                existing = cursor.fetchone()

                if existing:
                    flash("A comment already exists for this teacher, stream, and score range.", "warning")
                else:
                    cursor.execute("""
                        INSERT INTO classteacher_comments (
                            user_id, stream_id, min_score, max_score, comment, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        teacher_user_id, stream_id, min_score, max_score, comment, now, now
                    ))
                    connection.commit()
                    flash("Class teacher comment added successfully.", "success")
                    return redirect(url_for('classteacher_comments_blueprint.add_classteacher_comments'))

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'classteacher_comments/add_classteacher_comments.html',
        streams=streams,
        segment='add_classteacher_comments'
    )










@blueprint.route('/edit_classteacher_comments/<int:comment_id>', methods=['GET', 'POST'])
def edit_classteacher_comments(comment_id):
    """Edit an existing class teacher comment for the logged-in user."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    logged_in_user_id = session.get('id')
    if not logged_in_user_id:
        flash("You must be logged in to edit comments.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    # Fetch teacher user_ids assigned to the logged-in user
    cursor.execute("""
        SELECT DISTINCT user_id
        FROM classteacher_assignment
        WHERE user_id = %s
    """, (logged_in_user_id,))
    assigned_teachers = cursor.fetchall()
    if assigned_teachers:
        teacher_user_ids = [t['user_id'] for t in assigned_teachers]
    else:
        teacher_user_ids = [logged_in_user_id]

    # Fetch the comment ensuring it belongs to one of the teacher user_ids
    format_strings = ','.join(['%s'] * len(teacher_user_ids))
    query = f"""
        SELECT * FROM classteacher_comments
        WHERE comment_id = %s AND user_id IN ({format_strings})
    """
    params = [comment_id] + teacher_user_ids
    cursor.execute(query, params)
    comment_data = cursor.fetchone()

    if not comment_data:
        flash("Comment not found or access denied.", "danger")
        cursor.close()
        connection.close()
        return redirect(url_for('classteacher_comments_blueprint.classteacher_comments'))

    # Fetch streams for dropdown
    cursor.execute("SELECT stream_id, stream_name FROM stream ORDER BY stream_name")
    streams = cursor.fetchall()

    if request.method == 'POST':
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        comment = request.form.get('comment')
        stream_id = request.form.get('stream_id')
        updated_at = datetime.now()

        if not min_score or not max_score or not comment or not stream_id:
            flash("Please fill in all required fields.", "warning")
            return redirect(url_for('classteacher_comments_blueprint.edit_classteacher_comments', comment_id=comment_id))

        try:
            # Check for duplicate score range for same user but different comment_id
            cursor.execute(f'''
                SELECT * FROM classteacher_comments
                WHERE user_id IN ({format_strings}) 
                AND min_score = %s AND max_score = %s 
                AND stream_id = %s AND comment_id != %s
            ''', teacher_user_ids + [min_score, max_score, stream_id, comment_id])
            existing = cursor.fetchone()

            if existing:
                flash("A comment already exists for this stream and score range.", "warning")
                return redirect(url_for('classteacher_comments_blueprint.edit_classteacher_comments', comment_id=comment_id))

            # Update the comment
            cursor.execute('''
                UPDATE classteacher_comments
                SET stream_id = %s, min_score = %s, max_score = %s, comment = %s, updated_at = %s
                WHERE comment_id = %s AND user_id IN ({})
            '''.format(format_strings),
            [stream_id, min_score, max_score, comment, updated_at, comment_id] + teacher_user_ids)
            connection.commit()

            flash("Comment updated successfully!", "success")
            return redirect(url_for('classteacher_comments_blueprint.classteacher_comments'))

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'classteacher_comments/edit_classteacher_comments.html',
        comment=comment_data,
        streams=streams,
        segment='classteacher_comments'
    )










@blueprint.route('/delete_classteacher_comments/<int:comment_id>')
def delete_classteacher_comments(comment_id):
    """Deletes a class teacher comment if it belongs to the logged-in user."""
    user_id = session.get('id')
    if not user_id:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Verify comment exists and belongs to current user
        cursor.execute(
            "SELECT * FROM classteacher_comments WHERE comment_id = %s AND user_id = %s",
            (comment_id, user_id)
        )
        comment = cursor.fetchone()

        if not comment:
            flash("Comment not found or you do not have permission to delete it.", "warning")
            return redirect(url_for('classteacher_comments_blueprint.classteacher_comments'))

        # Perform deletion
        cursor.execute(
            "DELETE FROM classteacher_comments WHERE comment_id = %s AND user_id = %s",
            (comment_id, user_id)
        )
        connection.commit()
        flash("Comment deleted successfully.", "success")

    except mysql.connector.Error as err:
        flash(f"Database error occurred while deleting the comment: {err}", "danger")

    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('classteacher_comments_blueprint.classteacher_comments'))



@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("classteacher_comments/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'classteacher_comments'

        return segment

    except:
        return None
