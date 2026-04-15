from apps.rooms import blueprint
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









@blueprint.route('/rooms')
def rooms():
    """Fetches all rooms and renders the manage rooms page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all rooms from the database
    cursor.execute('SELECT * FROM rooms')
    rooms = cursor.fetchall()

    # Close the cursor and connection
    cursor.close()
    connection.close()

    return render_template('rooms/rooms.html', rooms=rooms,segment='rooms')







@blueprint.route('/add_room', methods=['GET', 'POST'])
def add_room():
    """Handles the adding of a new room."""
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        capacity = request.form.get('capacity')
        description = request.form.get('description')

        # Validate input
        if not room_name or not capacity:
            flash("Please fill out all required fields!", "warning")
        elif not re.match(r'^[0-9]+$', capacity):  # Ensure capacity is a valid number
            flash('Capacity must be a valid number!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the room already exists
                cursor.execute('SELECT * FROM rooms WHERE room_name = %s', (room_name,))
                existing_room = cursor.fetchone()

                if existing_room:
                    flash("Room with this name already exists!", "warning")
                else:
                    # Insert the new room into the database
                    cursor.execute('''
                        INSERT INTO rooms (room_name, capacity, description)
                        VALUES (%s, %s, %s)
                    ''', (room_name, capacity, description))
                    connection.commit()
                    flash("Room successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Error: {err}", "danger")
            finally:
                cursor.close()
                connection.close()

    return render_template('rooms/add_room.html', segment='add_room')








@blueprint.route('/edit_room/<int:room_id>', methods=['GET', 'POST'])
def edit_room(room_id):
    """Handles editing an existing room."""
    if request.method == 'POST':
        # Retrieve form data
        room_name = request.form['room_name']
        capacity = request.form['capacity']
        description = request.form['description']

        # Validate the input
        if not room_name or not capacity:
            flash("Please fill out all required fields!", "warning")
            return redirect(url_for('rooms_blueprint.edit_room', room_id=room_id))

        if not re.match(r'^[0-9]+$', capacity):
            flash("Capacity must be a valid number!", "danger")
            return redirect(url_for('rooms_blueprint.edit_room', room_id=room_id))

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Check if a room with the same name exists (excluding current room)
            cursor.execute("""
                SELECT * FROM rooms 
                WHERE room_name = %s AND room_id != %s
            """, (room_name, room_id))
            existing_room = cursor.fetchone()

            if existing_room:
                flash("A room with this name already exists!", "warning")
                return redirect(url_for('rooms_blueprint.edit_room', room_id=room_id))

            # Update the room
            cursor.execute("""
                UPDATE rooms
                SET room_name = %s, capacity = %s, description = %s
                WHERE room_id = %s
            """, (room_name, capacity, description, room_id))
            connection.commit()

            flash("Room updated successfully!", "success")

        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('rooms_blueprint.rooms'))

    elif request.method == 'GET':
        # Retrieve room details for pre-filling the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM rooms WHERE room_id = %s", (room_id,))
        room_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if room_data:
            return render_template('rooms/edit_room.html', room=room_data, segment='rooms')
        else:
            flash("Room not found.", "danger")
            return redirect(url_for('rooms_blueprint.rooms'))







@blueprint.route('/delete_room/<int:room_id>')
def delete_room(room_id):
    """Deletes a room from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the room with the specified ID
        cursor.execute('DELETE FROM rooms WHERE room_id = %s', (room_id,))
        connection.commit()
        flash("Room deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('rooms_blueprint.rooms'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("rooms/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'rooms'

        return segment

    except:
        return None
