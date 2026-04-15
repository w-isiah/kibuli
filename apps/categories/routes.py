from apps.categories import blueprint
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



@blueprint.route('/categories')
def categories():
    """Fetches all categories and renders the manage categories page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all categories from the database
    cursor.execute('SELECT * FROM category_list')
    categories = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('categories/categories.html', categories=categories,segment='categories')







@blueprint.route('/add_category', methods=['GET', 'POST'])
def add_category():
    """Handles the adding of a new category."""
    if request.method == 'POST':
        name = request.form.get('name')

        # Validate input
        if not name:
            flash("Please fill out the form!", "warning")
        elif not re.match(r'^[A-Za-z0-9_ ]+$', name):

            flash('Deaprtment name must contain only letters and numbers!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the category already exists
                cursor.execute('SELECT * FROM category_list WHERE name = %s', (name,))
                existing_category = cursor.fetchone()

                if existing_category:
                    flash("Department already exists!", "warning")
                else:
                    # Insert the new category into the database
                    cursor.execute('INSERT INTO category_list (name) VALUES (%s)', (name,))
                    connection.commit()
                    flash("Department successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('categories/add_category.html',segment='add_category')











@blueprint.route('/edit_category/<int:category_id>', methods=['GET', 'POST'])
def edit_category(category_id):
    """Handles editing an existing category."""
    if request.method == 'POST':
        name = request.form['name']

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Update category in the database
            cursor.execute("""
                UPDATE category_list
                SET name = %s
                WHERE CategoryID = %s
            """, (name, category_id))
            connection.commit()

            flash("Department updated successfully!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('categories_blueprint.categories'))

    elif request.method == 'GET':
        # Retrieve the category to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM category_list WHERE CategoryID = %s", (category_id,))
        category = cursor.fetchone()
        cursor.close()
        connection.close()

        if category:
            return render_template('categories/edit_category.html', category=category,segment='categories')
        else:
            flash("Department not found.", "danger")
            return redirect(url_for('categories_blueprint.categories'))


@blueprint.route('/delete_category/<int:category_id>')
def delete_category(category_id):
    """Deletes a category from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the category with the specified ID
        cursor.execute('DELETE FROM category_list WHERE CategoryID = %s', (category_id,))
        connection.commit()
        flash("Department deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('categories_blueprint.categories'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("categories/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'categories'

        return segment

    except:
        return None
