from apps.dorms import blueprint
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



@blueprint.route('/dorms')
def dorms():
    """Fetches all dorms, their associated rooms, and dorm masters (teachers), and renders the manage dorms page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # SQL query to fetch all dorms with their associated rooms and dorm masters (teachers)
    cursor.execute('''
        SELECT dormitories.dormitory_id, dormitories.name AS dorm_name, dormitories.gender, 
               dormitories.description AS dorm_description, dormitories.dorm_master_id,
               rooms.room_id, rooms.room_name, rooms.capacity AS room_capacity, rooms.description AS room_description,
               teachers.first_name AS teacher_first_name, teachers.last_name AS teacher_last_name
        FROM dormitories
        LEFT JOIN rooms ON dormitories.room_id = rooms.room_id
        LEFT JOIN teachers ON dormitories.dorm_master_id = teachers.teacher_id
    ''')

    dorms = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('dorms/dorms.html', dorms=dorms, segment='dorms')







@blueprint.route('/add_dorms', methods=['GET', 'POST'])
def add_dorms():
    """
    Handles the adding of a new dormitory. 
    Fetches users with role='matron' for the Dorm Master dropdown.
    """
    connection = get_db_connection()
    try:
        cursor = connection.cursor(dictionary=True)

        # 1. Fetch all rooms for the room dropdown
        cursor.execute('SELECT * FROM rooms')
        rooms = cursor.fetchall()

        # 2. FIX: Fetch Matrons (users with role='matron') for the Dorm Master dropdown
        # ASSUMPTION: The 'users' table has columns 'id', 'first_name', 'last_name', and 'role'.
        # We alias 'id' to 'teacher_id' and the names to maintain compatibility with existing template structure.
        cursor.execute("""
            SELECT 
                id AS teacher_id, 
                first_name, 
                last_name 
            FROM users 
            WHERE role = 'metron' or role = 'dorm_master'
            ORDER BY last_name
        """)
        # We reuse the 'teachers' variable name to minimize template changes
        teachers = cursor.fetchall() 

        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            gender = request.form.get('gender', '').strip()
            description = request.form.get('description', '').strip()
            # Note: dorm_master_id now refers to the user.id of the Matron
            dorm_master_id = request.form.get('dorm_master_id', '').strip()
            room_id = request.form.get('room_id', '').strip()

            # Validate required fields
            if not name or not gender or not room_id:
                flash("Please fill out all required fields!", "warning")
                
            # The room_id check is kept here, but remember this is a design flaw!
            elif room_id and not room_id.isdigit():
                flash("Room ID must be numeric!", "danger")
            
            # dorm_master_id validation is updated to check if it's numeric when provided
            elif dorm_master_id and not dorm_master_id.isdigit():
                flash("Dorm Master ID must be numeric if provided!", "danger")

            else:
                try:
                    # Check for existing dorm with same name and gender
                    cursor.execute(
                        'SELECT dormitory_id FROM dormitories WHERE name = %s AND gender = %s',
                        (name, gender)
                    )
                    if cursor.fetchone():
                        flash("Dormitory already exists with that name and gender!", "warning")

                    else:
                        # Check if selected room is already allocated (Retained for existing schema logic)
                        cursor.execute(
                            'SELECT dormitory_id FROM dormitories WHERE room_id = %s',
                            (room_id,)
                        )
                        if cursor.fetchone():
                            flash("Selected room is already allocated to another dormitory! (Fix your database schema for rooms!)", "danger")
                        else:
                            # Insert new dormitory
                            # Prepare values, handling the optional dorm_master_id and mandatory room_id
                            master_id_val = int(dorm_master_id) if dorm_master_id else None
                            room_id_val = int(room_id)

                            cursor.execute(
                                '''
                                INSERT INTO dormitories (name, gender, description, dorm_master_id, room_id)
                                VALUES (%s, %s, %s, %s, %s)
                                ''',
                                (
                                    name,
                                    gender,
                                    description,
                                    master_id_val,
                                    room_id_val
                                )
                            )
                            connection.commit()
                            flash("Dormitory successfully added!", "success")
                            return redirect(url_for('dorms_blueprint.dorms'))

                except mysql.connector.Error as err:
                    logging.error(f"Database error during dormitory insertion: {err}")
                    flash(f"Database error: Could not add dormitory.", "danger")
                    # Rerun fetch to repopulate dropdowns in case of error (optional, but cleaner)
                    return redirect(url_for('dorms_blueprint.add_dorms'))


    except Error as e:
        logging.error(f"Error fetching initial data: {e}")
        flash('An error occurred while preparing the form data.', 'danger')
        # Ensure rooms and teachers are defined to avoid errors when rendering the template
        rooms = []
        teachers = []
        
    finally:
        # Cleanup
        if 'cursor' in locals() and cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

    return render_template(
        'dorms/add_dorms.html',
        teachers=teachers, # Now holds matrons/users
        rooms=rooms,
        segment='add_dorms'
    )



@blueprint.route('/edit_dorms/<int:dorm_id>', methods=['GET', 'POST'])
def edit_dorms(dorm_id):
    """Handles editing an existing dormitory record."""

    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', '').strip()
        
        # Note: 'capacity' is not present in your other dorm routes, but kept here for schema compatibility.
        capacity = request.form.get('capacity', '').strip() 
        description = request.form.get('description', '').strip()
        
        # Handle optional fields: convert empty string to None
        dorm_master_id_str = request.form.get('dorm_master_id')
        room_id_str = request.form.get('room_id')

        # Convert to None if empty string is passed (e.g., if a dropdown is optional)
        dorm_master_id = int(dorm_master_id_str) if dorm_master_id_str and dorm_master_id_str.isdigit() else None
        room_id = int(room_id_str) if room_id_str and room_id_str.isdigit() else None
        
        # --- Validation ---
        if not name or not gender:
            flash("Dormitory Name and Gender are required fields!", "warning")
            return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

        if capacity and not capacity.isdigit():
            flash("Capacity must be a valid number.", "danger")
            return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))
        # --- End Validation ---

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Check for duplicate name/gender, excluding the current dorm
            cursor.execute("""
                SELECT dormitory_id FROM dormitories
                WHERE name = %s AND gender = %s AND dormitory_id != %s
            """, (name, gender, dorm_id))
            if cursor.fetchone():
                flash("A dormitory with the same name and gender already exists!", "warning")
                return redirect(url_for('dorms_blueprint.edit_dorms', dorm_id=dorm_id))

            # Update dormitory
            # Note: capacity is only updated if it was provided and numeric
            capacity_val = int(capacity) if capacity and capacity.isdigit() else None
            
            cursor.execute("""
                UPDATE dormitories
                SET name = %s, gender = %s, capacity = %s, description = %s,
                    dorm_master_id = %s, room_id = %s
                WHERE dormitory_id = %s
            """, (name, gender, capacity_val, description or None,
                  dorm_master_id, room_id, dorm_id))
            
            connection.commit()
            flash("Dormitory updated successfully!", "success")

        except Exception as e:
            logging.error(f"Database error during dormitory update: {e}")
            flash(f"An error occurred while updating the dormitory.", "danger")

        finally:
            if 'cursor' in locals(): cursor.close()
            if 'connection' in locals() and connection.is_connected(): connection.close()

        return redirect(url_for('dorms_blueprint.dorms'))

    else:  # GET request
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Fetch dorm data
            cursor.execute("SELECT * FROM dormitories WHERE dormitory_id = %s", (dorm_id,))
            dorm = cursor.fetchone()

            if not dorm:
                flash("Dormitory not found.", "danger")
                return redirect(url_for('dorms_blueprint.dorms'))

            # FIX: Fetch Matrons/Dorm Masters (users) for the dropdown
            # Alias 'id' to 'teacher_id' for template compatibility
            # Filter by role: 'matron' or 'dorm_master'
            cursor.execute("""
                SELECT 
                    id AS teacher_id, 
                    first_name, 
                    last_name 
                FROM users 
                WHERE role IN ('matron', 'dorm_master')
                ORDER BY last_name
            """)
            teachers = cursor.fetchall() # Variable name kept as 'teachers' for template compatibility

            # Fetch rooms for dropdown
            cursor.execute("SELECT room_id, room_name FROM rooms ORDER BY room_name")
            rooms = cursor.fetchall()

        except Exception as e:
            logging.error(f"Failed to retrieve data for edit form: {e}")
            flash("Failed to retrieve dormitory or dropdown data.", "danger")
            # Ensure variables are defined even on error
            dorm, teachers, rooms = None, [], [] 
            return redirect(url_for('dorms_blueprint.dorms'))

        finally:
            if 'cursor' in locals(): cursor.close()
            if 'connection' in locals() and connection.is_connected(): connection.close()

        return render_template(
            'dorms/edit_dorms.html',
            dorm=dorm,
            teachers=teachers, # Now holds matrons/users
            rooms=rooms,
            segment='dorms'
        )








@blueprint.route('/delete_dorms/<int:dormitory_id>')
def delete_dorms(dormitory_id):
    """Deletes a dormitory record from the database."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if the dormitory exists before deletion
        cursor.execute("SELECT * FROM dormitories WHERE dormitory_id = %s", (dormitory_id,))
        dorm = cursor.fetchone()

        if not dorm:
            flash("Dormitory not found.", "warning")
        else:
            cursor.execute("DELETE FROM dormitories WHERE dormitory_id = %s", (dormitory_id,))
            connection.commit()
            flash("Dormitory deleted successfully.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the dormitory: {e}", "danger")

    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return redirect(url_for('dorms_blueprint.dorms'))
   





@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("dorms/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'dorms'

        return segment

    except:
        return None
