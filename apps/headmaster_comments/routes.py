from apps.headmaster_comments import blueprint
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




@blueprint.route('/headmaster_comments')
def headmaster_comments():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch headmaster comments with teacher info
    cursor.execute("""
        SELECT hc.comment_id,
               hc.min_score,
               hc.max_score,
               hc.comment,
               hc.created_at,
               hc.updated_at,
               CONCAT(u.first_name, ' ', u.last_name,
                      IF(u.other_name IS NOT NULL AND u.other_name != '', CONCAT(' ', u.other_name), '')
               ) AS teacher_name
        FROM headmaster_comments hc
        LEFT JOIN users u ON hc.user_id = u.id
        ORDER BY hc.min_score
    """)
    headmaster_comments = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('headmaster_comments/headmaster_comments.html',
                           headmaster_comments=headmaster_comments,
                           segment='headmaster_comments')









from flask import session, redirect, url_for, request, render_template, flash
from datetime import datetime

@blueprint.route('/add_headmaster_comments', methods=['GET', 'POST'])
def add_headmaster_comments():
    """Handles adding a new headmaster comment (linked to current user)."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    user_id = session.get('id')  # Ensure this key exists in your login session
    if not user_id:
        flash("You must be logged in to add a comment.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    if request.method == 'POST':
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        comment = request.form.get('comment')
        now = datetime.now()

        # Validate input
        if not min_score or not max_score or not comment:
            flash("Please fill in all required fields.", "warning")
        else:
            try:
                # Optional: check if a similar comment exists for this user
                cursor.execute('''
                    SELECT * FROM headmaster_comments
                    WHERE user_id = %s AND min_score = %s AND max_score = %s
                ''', (user_id, min_score, max_score))
                existing = cursor.fetchone()

                if existing:
                    flash("A comment already exists for this score range.", "warning")
                else:
                    cursor.execute('''
                        INSERT INTO headmaster_comments (
                            user_id, min_score, max_score, comment, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (
                        user_id, min_score, max_score, comment, now, now
                    ))
                    connection.commit()
                    flash("Headmaster comment added successfully.", "success")
                    return redirect(url_for('headmaster_comments_blueprint.add_headmaster_comments'))
            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'headmaster_comments/add_headmaster_comments.html',
        segment='add_headmaster_comments'
    )











@blueprint.route('/edit_headmaster_comments/<int:comment_id>', methods=['GET', 'POST'])
def edit_headmaster_comments(comment_id):
    """Edit an existing headmaster comment for the logged-in user."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    user_id = session.get('id')
    if not user_id:
        flash("You must be logged in to edit comments.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    # Fetch existing comment
    cursor.execute("SELECT * FROM headmaster_comments WHERE comment_id = %s AND user_id = %s", (comment_id, user_id))
    comment_data = cursor.fetchone()

    if not comment_data:
        flash("Comment not found or access denied.", "danger")
        cursor.close()
        connection.close()
        return redirect(url_for('headmaster_comments_blueprint.headmaster_comments'))

    if request.method == 'POST':
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        comment = request.form.get('comment')
        updated_at = datetime.now()

        if not min_score or not max_score or not comment:
            flash("Please fill in all required fields.", "warning")
            return redirect(url_for('headmaster_comments_blueprint.edit_headmaster_comments', comment_id=comment_id))

        try:
            # Check for duplicate score range for same user
            cursor.execute('''
                SELECT * FROM headmaster_comments
                WHERE user_id = %s AND min_score = %s AND max_score = %s AND comment_id != %s
            ''', (user_id, min_score, max_score, comment_id))
            existing = cursor.fetchone()

            if existing:
                flash("A comment already exists for this score range.", "warning")
                return redirect(url_for('headmaster_comments_blueprint.edit_headmaster_comments', comment_id=comment_id))

            # Update the comment
            cursor.execute('''
                UPDATE headmaster_comments
                SET min_score = %s, max_score = %s, comment = %s, updated_at = %s
                WHERE comment_id = %s AND user_id = %s
            ''', (min_score, max_score, comment, updated_at, comment_id, user_id))
            connection.commit()

            flash("Comment updated successfully!", "success")
            return redirect(url_for('headmaster_comments_blueprint.headmaster_comments'))

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'headmaster_comments/edit_headmaster_comments.html',
        comment=comment_data,
        segment='headmaster_comments'
    )










@blueprint.route('/delete_headmaster_comments/<int:comment_id>')
def delete_headmaster_comments(comment_id):
    """Deletes a headmaster comment from the database if it belongs to the current user."""
    if 'user_id' not in session:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for('auth_blueprint.login'))

    user_id = session['user_id']
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Check if comment exists and belongs to the current user
        cursor.execute("SELECT * FROM headmaster_comments WHERE comment_id = %s AND user_id = %s", (comment_id, user_id))
        comment = cursor.fetchone()

        if not comment:
            flash("Comment not found or you do not have permission to delete it.", "warning")
            return redirect(url_for('headmaster_comments_blueprint.headmaster_comments'))

        # Delete the comment
        cursor.execute("DELETE FROM headmaster_comments WHERE comment_id = %s AND user_id = %s", (comment_id, user_id))
        connection.commit()
        flash("Comment deleted successfully.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the comment: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('headmaster_comments_blueprint.headmaster_comments'))



@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("headmaster_comments/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'headmaster_comments'

        return segment

    except:
        return None
