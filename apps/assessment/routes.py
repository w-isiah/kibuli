from apps.assessment import blueprint
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

from datetime import datetime
import pytz

def get_kampala_time():
    kampala = pytz.timezone("Africa/Kampala")
    return datetime.now(kampala)


@blueprint.route('/assessment')
def assessment():
    """Fetches all assessments and renders the manage assessment page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all assessments from the database
    cursor.execute('SELECT assessment_id, assessment_name, description FROM assessment')
    assessments = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template(
        'assessment/assessment.html',
        assessment=assessments,
        segment='assessment'
    )







@blueprint.route('/add_assessment', methods=['GET', 'POST'])
def add_assessment():
    """Handles adding a new assessment and logs the action."""
    if request.method == 'POST':
        assessment_name = request.form.get('assessment_name')
        description = request.form.get('description')

        # Basic validation
        if not assessment_name or not description:
            flash("Please fill out all required fields!", "warning")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the assessment already exists
                cursor.execute('SELECT * FROM assessment WHERE assessment_name = %s', (assessment_name,))
                existing = cursor.fetchone()

                if existing:
                    flash("An assessment with that name already exists!", "warning")
                else:
                    # Insert new assessment
                    cursor.execute(
                        '''
                        INSERT INTO assessment (assessment_name, description)
                        VALUES (%s, %s)
                        ''',
                        (assessment_name, description)
                    )
                    connection.commit()

                    # Retrieve the new assessment ID
                    assessment_id = cursor.lastrowid

                    # Prepare log info
                    created_by = session.get('username', 'unknown')
                    user_id = session.get('id', 'unknown')  # assuming 'id' is the session key for user ID
                    created_at = get_kampala_time()

                    # Insert into add_assessment_logs for audit trail
                    cursor.execute(
                        '''
                        INSERT INTO add_assessment_logs 
                        (assessment_id, assessment_name, description, created_by, created_at, user_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ''',
                        (assessment_id, assessment_name, description, created_by, created_at, user_id)
                    )
                    connection.commit()

                    flash("Assessment successfully added and logged!", "success")

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('assessment/add_assessment.html', segment='add_assessment')












@blueprint.route('/edit_assessment/<int:assessment_id>', methods=['GET', 'POST'])
def edit_assessment(assessment_id):
    """Handles editing an existing assessment."""
    if request.method == 'POST':
        # Retrieve the form data
        assessment_name = request.form['assessment_name']
        description = request.form.get('description')  # Optional field

        # Validate the input
        if not assessment_name:
            flash("Please fill out the assessment name!", "warning")
            return redirect(url_for('assessment_blueprint.edit_assessment', assessment_id=assessment_id))

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Retrieve the old assessment data for logging (optional, if you want to track changes)
            cursor.execute("SELECT * FROM assessment WHERE assessment_id = %s", (assessment_id,))
            old_assessment = cursor.fetchone()

            if not old_assessment:
                flash("Assessment not found.", "danger")
                return redirect(url_for('assessment_blueprint.assessment'))

            # Optional: Check if a different assessment already has the same name (if uniqueness is required)
            cursor.execute("""
                SELECT * FROM assessment 
                WHERE assessment_name = %s AND assessment_id != %s
            """, (assessment_name, assessment_id))
            existing_assessment = cursor.fetchone()

            if existing_assessment:
                flash("An assessment with this name already exists!", "warning")
                return redirect(url_for('assessment_blueprint.edit_assessment', assessment_id=assessment_id))

            # Update the assessment details
            cursor.execute("""
                UPDATE assessment
                SET assessment_name = %s, description = %s
                WHERE assessment_id = %s
            """, (assessment_name, description, assessment_id))
            connection.commit()

            # Optional: Insert into edit_assessment_logs for audit trail
            user_id = session.get('id')
            edited_at = get_kampala_time()

            cursor.execute("""
                INSERT INTO edit_assessment_logs 
                (assessment_id, old_assessment_name, new_assessment_name, old_description, new_description, edited_at, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                assessment_id,
                old_assessment['assessment_name'], assessment_name,
                old_assessment['description'], description,
                edited_at, user_id
            ))
            connection.commit()

            flash("Assessment updated successfully!", "success")

        except mysql.connector.Error as err:
            flash(f"Database Error: {err}", "danger")
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('assessment_blueprint.assessment'))

    else:  # GET method
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM assessment WHERE assessment_id = %s", (assessment_id,))
        assessment_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if assessment_data:
            return render_template('assessment/edit_assessment.html', assessment=assessment_data, segment='assessment')
        else:
            flash("Assessment not found.", "danger")
            return redirect(url_for('assessment_blueprint.assessment'))









@blueprint.route('/delete_assessment/<int:assessment_id>')
def delete_assessment(assessment_id):
    """Deletes an assessment from the database and logs the deletion."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Check if assessment exists
        cursor.execute("SELECT * FROM assessment WHERE assessment_id = %s", (assessment_id,))
        assessment = cursor.fetchone()

        if not assessment:
            flash("Assessment not found.", "warning")
            return redirect(url_for('assessment_blueprint.assessment'))

        # Prepare log data
        assessment_name = assessment.get('assessment_name', '') or ''
        description = assessment.get('description', '') or ''
        deleted_at = datetime.now()
        user_id = session.get('user_id', 'unknown')

        # Insert deletion log before deleting
        cursor.execute("""
            INSERT INTO delete_assessment_logs 
            (assessment_id, assessment_name, description, deleted_at, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (assessment_id, assessment_name, description, deleted_at, user_id))
        connection.commit()

        # Delete the assessment
        cursor.execute("DELETE FROM assessment WHERE assessment_id = %s", (assessment_id,))
        connection.commit()

        flash("Assessment deleted successfully and deletion logged.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the assessment: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('assessment_blueprint.assessment'))








@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("assessment/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'assessment'

        return segment

    except:
        return None
