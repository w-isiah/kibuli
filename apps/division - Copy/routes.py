from apps.division import blueprint
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



@blueprint.route('/division')
def division():
    """Fetches all divisions and renders the manage division page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all divisions from the database
    cursor.execute('SELECT * FROM division')
    divisions = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('division/division.html', divisions=divisions, segment='division')








@blueprint.route('/add_division', methods=['GET', 'POST'])
def add_division():
    """Handles the adding of a new division."""
    if request.method == 'POST':
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        division_name = request.form.get('division_name')  # e.g., '1', '2', '3', 'U'

        # Validate input
        if not min_score or not max_score or not division_name:
            flash("Please fill out all required fields!", "warning")
        elif not min_score.isdigit() or not max_score.isdigit():
            flash("Scores must be valid numbers!", "danger")
        elif len(division_name) > 2:
            flash("Division name must be 1 or 2 characters!", "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the division already exists
                cursor.execute(
                    'SELECT * FROM division WHERE division_name = %s AND min_score = %s AND max_score = %s',
                    (division_name, min_score, max_score)
                )
                existing_div = cursor.fetchone()

                if existing_div:
                    flash("This division already exists for the specified score range!", "warning")
                else:
                    # Insert the new division into the database
                    cursor.execute(''' 
                        INSERT INTO division (division_name, min_score, max_score) 
                        VALUES (%s, %s, %s)
                    ''', (division_name, min_score, max_score))
                    connection.commit()
                    flash("Division successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Database Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('division/add_division.html', segment='add_division')














@blueprint.route('/edit_division/<int:division_id>', methods=['GET', 'POST'])
def edit_division(division_id):
    """Handles editing an existing division."""
    if request.method == 'POST':
        # Get form data
        division_name = request.form['division_name']
        min_score = request.form['min_score']
        max_score = request.form['max_score']

        # Validate inputs
        if not division_name or not min_score or not max_score:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('division_blueprint.edit_division', division_id=division_id))

        if not min_score.isdigit() or not max_score.isdigit():
            flash("Scores must be valid numbers!", "danger")
            return redirect(url_for('division_blueprint.edit_division', division_id=division_id))

        if len(division_name) > 2:
            flash("Division name must be 1 or 2 characters!", "danger")
            return redirect(url_for('division_blueprint.edit_division', division_id=division_id))

        try:
            min_score = int(min_score)
            max_score = int(max_score)

            connection = get_db_connection()
            cursor = connection.cursor()

            # Check for duplicate division
            cursor.execute("""
                SELECT * FROM division 
                WHERE division_name = %s AND division_id != %s
            """, (division_name, division_id))
            existing_division = cursor.fetchone()

            if existing_division:
                flash("A division with the same name already exists!", "warning")
                return redirect(url_for('division_blueprint.edit_division', division_id=division_id))

            # Perform update
            cursor.execute("""
                UPDATE division
                SET division_name = %s, min_score = %s, max_score = %s
                WHERE division_id = %s
            """, (division_name, min_score, max_score, division_id))
            connection.commit()
            flash("Division updated successfully!", "success")

        except mysql.connector.Error as err:
            flash(f"Database Error: {err}", "danger")
        except Exception as e:
            flash(f"An error occurred: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('division_blueprint.division'))

    elif request.method == 'GET':
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM division WHERE division_id = %s", (division_id,))
        division_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if division_data:
            return render_template('division/edit_division.html', division=division_data, segment='division')
        else:
            flash("Division not found.", "danger")
            return redirect(url_for('division_blueprint.division'))


















@blueprint.route('/delete_division/<int:grade_id>')
def delete_division(grade_id):
    """Deletes a grade from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Check if grade exists
        cursor.execute("SELECT * FROM division WHERE grade_id = %s", (grade_id,))
        grade = cursor.fetchone()

        if not grade:
            flash("Grade not found.", "warning")
            return redirect(url_for('division_blueprint.division'))

        # Proceed with deletion
        cursor.execute("DELETE FROM division WHERE grade_id = %s", (grade_id,))
        connection.commit()
        flash("Grade deleted successfully.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the grade: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('division_blueprint.division'))





@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("division/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'division'

        return segment

    except:
        return None
