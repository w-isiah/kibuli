# Assuming your blueprint is defined in an 'apps.locations' module 
# and aliased to 'locations_blueprint'
from apps.locations import blueprint 

from flask import render_template, request, redirect, url_for, flash, session
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
import re
from apps import get_db_connection
from jinja2 import TemplateNotFound



@blueprint.route('/locations')
def locations():
    """Fetches all locations and renders the Manage Locations page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch all locations, including room_id and description
    cursor.execute("""
        SELECT 
            l.LocationID,
            l.LocationName,
            l.room_id,
            r.room_name,
            l.description
        FROM locations l
        LEFT JOIN rooms r ON l.room_id = r.room_id
        ORDER BY l.LocationName ASC
    """)
    locations = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('locations/locations.html', locations=locations)







import re
# Assuming mysql.connector is imported or accessible

@blueprint.route('/add_location', methods=['GET', 'POST'])
def add_location():
    """Handles adding a new location with optional room and description."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch available rooms for the dropdown
    cursor.execute('SELECT * FROM rooms ORDER BY room_name ASC')
    rooms = cursor.fetchall()

    if request.method == 'POST':
        location_name = request.form.get('name')
        room_id = request.form.get('room_id') or None  # Can be NULL
        description = request.form.get('description') or None

        # Validate input
        if not location_name:
            flash("Please fill out the form!", "warning")
        elif not re.match(r'^[A-Za-z0-9_ ]+$', location_name):
            flash('Location name must contain only letters and numbers!', "danger")
        else:
            try:
                # Check if the location already exists
                cursor.execute('SELECT * FROM locations WHERE LocationName = %s', (location_name,))
                existing_location = cursor.fetchone()

                if existing_location:
                    flash("Location already exists!", "warning")
                else:
                    # Insert the new location
                    cursor.execute(
                        'INSERT INTO locations (LocationName, room_id, description) VALUES (%s, %s, %s)',
                        (location_name, room_id, description)
                    )
                    connection.commit()
                    flash("Location successfully added!", "success")
            except mysql.connector.Error as err:
                flash(f"Database Error: {err}", "danger")
            except Exception as e:
                flash(f"An unexpected error occurred: {e}", "danger")
            finally:
                cursor.close()
                connection.close()
                return redirect(url_for('locations_blueprint.locations'))

    cursor.close()
    connection.close()
    return render_template('locations/add_location.html', rooms=rooms, segment='add_location')





@blueprint.route('/edit_location/<int:location_id>', methods=['GET', 'POST'])
def edit_location(location_id):
    """Handles editing an existing location."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        location_name = request.form.get('name')
        room_id = request.form.get('room_id') or None
        description = request.form.get('description') or None

        # Optional: Input validation for location name
        if not location_name or not re.match(r'^[A-Za-z0-9_ ]+$', location_name):
            flash("Invalid location name. Use letters, numbers, spaces, or underscores.", "danger")
            return redirect(url_for('locations_blueprint.edit_location', location_id=location_id))

        try:
            cursor.execute("""
                UPDATE locations
                SET LocationName = %s, room_id = %s, description = %s
                WHERE LocationID = %s
            """, (location_name, room_id, description, location_id))
            connection.commit()
            flash("Location updated successfully!", "success")
        except Exception as e:
            flash(f"Error updating location: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('locations_blueprint.locations'))

    else:  # GET
        # Fetch location to pre-fill the form
        cursor.execute("SELECT LocationID, LocationName, room_id, description FROM locations WHERE LocationID = %s", (location_id,))
        location = cursor.fetchone()

        # Fetch all rooms for dropdown
        cursor.execute("SELECT room_id, room_name FROM rooms ORDER BY room_name ASC")
        rooms = cursor.fetchall()
        cursor.close()
        connection.close()

        if location:
            return render_template('locations/edit_location.html', location=location, rooms=rooms, segment='locations')
        else:
            flash("Location not found.", "danger")
            return redirect(url_for('locations_blueprint.locations'))


@blueprint.route('/delete_location/<int:location_id>')
def delete_location(location_id):
    """Deletes a location from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute('DELETE FROM locations WHERE LocationID = %s', (location_id,))
        connection.commit()
        flash("Location deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: Cannot delete location. It may be linked to existing assets. ({str(e)})", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('locations_blueprint.locations'))
