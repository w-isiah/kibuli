from apps.study_years import blueprint
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



@blueprint.route('/study_years')
def study_years():
    """Fetches all study_years and renders the manage study_years page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all study_years from the database
    cursor.execute('SELECT * FROM study_year')
    study_years = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('study_years/study_years.html', study_years=study_years,segment='study_years')




@blueprint.route('/add_study_years', methods=['GET', 'POST'])
def add_study_years():
    """Handles the adding of a new study year."""
    if request.method == 'POST':
        year_name = request.form.get('year_name')
        level = request.form.get('level')

        # Validate input
        if not year_name or not level:
            flash("Please fill out all required fields!", "warning")
        elif not re.match(r'^[0-9]+$', level):
            flash('Level must be a valid number!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the year_name already exists for the same level
                cursor.execute(
                    'SELECT * FROM study_year WHERE year_name = %s AND level = %s',
                    (year_name, level)
                )
                existing_year = cursor.fetchone()

                if existing_year:
                    flash("Study year with this name and level already exists!", "warning")
                else:
                    # Insert the new study year into the database
                    cursor.execute('''
                        INSERT INTO study_year (year_name, level)
                        VALUES (%s, %s)
                    ''', (year_name, level))
                    connection.commit()
                    flash("Study year successfully added!", "success")
                    return redirect(url_for('study_years_blueprint.study_years'))

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('study_years/add_study_year.html', segment='add_study_year')













@blueprint.route('/edit_study_year/<int:year_id>', methods=['GET', 'POST'])
def edit_study_year(year_id):
    """Handles editing an existing study year."""
    if request.method == 'POST':
        # Retrieve the form data
        year_name = request.form['year_name']
        level = request.form['level']

        # Validate the input
        if not year_name or not level:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('study_years_blueprint.edit_study_years', year_id=year_id))

        if not re.match(r'^[0-9]+$', level):
            flash("Level must be a valid number!", "danger")
            return redirect(url_for('study_years_blueprint.edit_study_years', year_id=year_id))

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Check if the study year name already exists in the database for the same level
            cursor.execute("""
                SELECT * FROM study_year 
                WHERE year_name = %s AND level = %s AND year_id != %s
            """, (year_name, level, year_id))
            existing_year = cursor.fetchone()

            if existing_year:
                flash("A study year with the same name and level already exists!", "warning")
                return redirect(url_for('study_years_blueprint.edit_study_years', year_id=year_id))

            # Update the study year details in the database
            cursor.execute("""
                UPDATE study_year
                SET year_name = %s, level = %s
                WHERE year_id = %s
            """, (year_name, level, year_id))
            connection.commit()

            flash("Study year updated successfully!", "success")

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('study_years_blueprint.study_years'))

    elif request.method == 'GET':
        # Retrieve the study year to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM study_year WHERE year_id = %s", (year_id,))
        study_year = cursor.fetchone()
        cursor.close()
        connection.close()

        if study_year:
            return render_template('study_years/edit_study_year.html', study_year=study_year, segment='study_year')
        else:
            flash("Study year not found.", "danger")
            return redirect(url_for('study_years_blueprint.study_years'))










@blueprint.route('/delete_study_years/<int:class_id>')
def delete_study_years(class_id):
    """Deletes a study_years from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the study_years with the specified ID
        cursor.execute('DELETE FROM study_years WHERE class_id = %s', (class_id,))
        connection.commit()
        flash("class deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('study_years_blueprint.study_years'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("study_years/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'study_years'

        return segment

    except:
        return None
