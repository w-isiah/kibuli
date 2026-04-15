from apps.grades import blueprint
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



@blueprint.route('/grades')
def grades():
    """Fetches all grades and renders the manage grades page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all grades from the database
    cursor.execute('SELECT * FROM grades')
    grades = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('grades/grades.html', grades=grades,segment='grades')






@blueprint.route('/add_grades', methods=['GET', 'POST'])
def add_grades():
    """Handles the adding of a new grade."""
    if request.method == 'POST':
        min_score = request.form.get('min_score')
        max_score = request.form.get('max_score')
        grade_letter = request.form.get('grade_letter')
        remark = request.form.get('remark')  # Optional field

        # Validate input
        if not min_score or not max_score or not grade_letter:
            flash("Please fill out all required fields!", "warning")
        elif not min_score.isdigit() or not max_score.isdigit():
            flash("Scores must be valid numbers!", "danger")
        #elif len(grade_letter) != 1:  # Validate that the grade letter is of length 1 (e.g., A, B, C)
        #    flash("Grade letter must be a single character!", "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the grade already exists
                cursor.execute('SELECT * FROM grades WHERE grade_letter = %s AND min_score = %s AND max_score = %s', 
                               (grade_letter, min_score, max_score))
                existing_grade = cursor.fetchone()  # Use fetchone for a single result

                if existing_grade:
                    flash("This grade already exists for the specified score range!", "warning")
                else:
                    # Insert the new grade into the database
                    cursor.execute(''' 
                        INSERT INTO grades (min_score, max_score, grade_letter, remark) 
                        VALUES (%s, %s, %s, %s)
                    ''', (min_score, max_score, grade_letter, remark if remark else None))
                    connection.commit()
                    flash("Grade successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('grades/add_grades.html', segment='add_grades')








@blueprint.route('/edit_grades/<int:grade_id>', methods=['GET', 'POST'])
def edit_grades(grade_id):
    """Handles editing an existing grade."""

    if request.method == 'POST':
        # Retrieve form data
        min_score = request.form['min_score']
        max_score = request.form['max_score']
        grade_letter = request.form['grade_letter']
        remark = request.form.get('remark')  # Optional
        weight = request.form['weight']

        # Validate required fields
        if not min_score or not max_score or not grade_letter or not weight:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('grades_blueprint.edit_grades', grade_id=grade_id))

        try:
            # Convert values to float for decimal support
            min_score = float(min_score)
            max_score = float(max_score)
            weight = float(weight)

            if min_score > max_score:
                flash("Minimum score cannot be greater than maximum score.", "warning")
                return redirect(url_for('grades_blueprint.edit_grades', grade_id=grade_id))

            connection = get_db_connection()
            cursor = connection.cursor()

            # Check for duplicate grade letter (excluding current record)
            cursor.execute("""
                SELECT * FROM grades 
                WHERE grade_letter = %s AND grade_id != %s
            """, (grade_letter, grade_id))
            existing_grade = cursor.fetchone()

            if existing_grade:
                flash("A grade with the same letter already exists!", "warning")
                return redirect(url_for('grades_blueprint.edit_grades', grade_id=grade_id))

            # Update grade in database
            cursor.execute("""
                UPDATE grades
                SET min_score = %s,
                    max_score = %s,
                    grade_letter = %s,
                    remark = %s,
                    weight = %s
                WHERE grade_id = %s
            """, (min_score, max_score, grade_letter, remark, weight, grade_id))
            connection.commit()

            flash("Grade updated successfully!", "success")

        except ValueError:
            flash("Scores and weight must be valid numbers (e.g., 79.99).", "danger")
        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")
        except Exception as e:
            flash(f"Unexpected error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('grades_blueprint.grades'))

    # GET request – prefill form
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM grades WHERE grade_id = %s", (grade_id,))
    grade_data = cursor.fetchone()

    cursor.close()
    connection.close()

    if not grade_data:
        flash("Grade not found.", "danger")
        return redirect(url_for('grades_blueprint.grades'))

    return render_template('grades/edit_grades.html', grade=grade_data, segment='grades')












@blueprint.route('/delete_grades/<int:grade_id>')
def delete_grades(grade_id):
    """Deletes a grade from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Check if grade exists
        cursor.execute("SELECT * FROM grades WHERE grade_id = %s", (grade_id,))
        grade = cursor.fetchone()

        if not grade:
            flash("Grade not found.", "warning")
            return redirect(url_for('grades_blueprint.grades'))

        # Proceed with deletion
        cursor.execute("DELETE FROM grades WHERE grade_id = %s", (grade_id,))
        connection.commit()
        flash("Grade deleted successfully.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the grade: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('grades_blueprint.grades'))





@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("grades/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'grades'

        return segment

    except:
        return None
