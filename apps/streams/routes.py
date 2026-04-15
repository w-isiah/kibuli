from apps.streams import blueprint
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

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import re
from datetime import datetime
import pytz


@blueprint.route('/streams')
def streams():
    """Fetches all streams including those with and without assigned teachers."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                stream.stream_id,
                stream.stream_name,
                stream.description,
                stream.created_at,
                stream.updated_at,
                stream.class_id,
                classes.class_name,
                rooms.room_name,
                users.username AS teacher_username
            FROM stream
            LEFT JOIN classes ON stream.class_id = classes.class_id
            LEFT JOIN rooms ON stream.room_id = rooms.room_id
            LEFT JOIN users ON users.id = stream.teacher_id
        """)
        streams = cursor.fetchall()

    except Exception as e:
        print(f"Database error: {e}")
        streams = []

    finally:
        cursor.close()
        connection.close()

    return render_template('streams/streams.html', streams=streams, segment='streams')










def get_kampala_time():
    return datetime.now(pytz.timezone("Africa/Kampala"))












@blueprint.route('/add_stream', methods=['GET', 'POST'])
def add_stream():
    """Handles creation of a new stream."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Fetch all teachers
        cursor.execute('SELECT username, id FROM users WHERE role = "teacher"')
        teachers = cursor.fetchall()

        if request.method == 'POST':
            # Extract form data
            stream_name = request.form.get('stream_name')
            class_id = request.form.get('class_id')
            room_id = request.form.get('room_id')
            teacher_id = request.form.get('teacher_id')
            description = request.form.get('description')
            user_id = session.get('id')
            now = get_kampala_time()

            # Validate required fields
            if not all([stream_name, class_id, user_id]):
                flash("Stream name, class, and user are required.", "warning")
                return redirect(url_for('streams_blueprint.add_stream'))

            # Check for duplicate stream in the same class
            cursor.execute(
                "SELECT 1 FROM stream WHERE stream_name = %s AND class_id = %s",
                (stream_name, class_id)
            )
            if cursor.fetchone():
                flash("A stream with this name already exists in the selected class.", "warning")
                return redirect(url_for('streams_blueprint.add_stream'))

            # Convert room_id and teacher_id to integers if present
            try:
                room_id_int = int(room_id) if room_id else None
                teacher_id_int = int(teacher_id) if teacher_id else None
            except ValueError:
                flash("Invalid room or teacher ID format. Please enter a numeric value.", "danger")
                return redirect(url_for('streams_blueprint.add_stream'))

            # Validate room assignment
            if room_id_int:
                cursor.execute("SELECT 1 FROM room_assignment WHERE room_id = %s", (room_id_int,))
                if cursor.fetchone():
                    flash("The selected room is already assigned.", "danger")
                    return redirect(url_for('streams_blueprint.add_stream'))

            # Insert new stream record
            cursor.execute(
                """
                INSERT INTO stream 
                (stream_name, class_id, teacher_id, room_id, description, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (stream_name, class_id, teacher_id_int, room_id_int, description, now, now)
            )
            stream_id = cursor.lastrowid

            # Assign room if applicable
            if room_id_int:
                cursor.execute(
                    """
                    INSERT INTO room_assignment 
                    (room_id, user_id, assigned_to_type, assigned_to_id, created_at, updated_at)
                    VALUES (%s, %s, 'stream', %s, %s, %s)
                    """,
                    (room_id_int, user_id, stream_id, now, now)
                )

            connection.commit()
            flash("Stream created successfully!", "success")
            return redirect(url_for('streams_blueprint.streams'))

        # GET request: load form data
        cursor.execute("SELECT class_id, class_name FROM classes")
        classes = cursor.fetchall()

        cursor.execute("SELECT room_id, room_name FROM rooms")
        rooms = cursor.fetchall()

        return render_template(
            'streams/add_stream.html',
            classes=classes,
            rooms=rooms,
            teachers=teachers,
            segment='streams'
        )

    except Exception as e:
        connection.rollback()
        flash(f"Database error: {e}", "danger")
        print(f"Database error: {e}")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('streams_blueprint.add_stream'))

















@blueprint.route('/edit_stream/<int:stream_id>', methods=['GET', 'POST'])
def edit_stream(stream_id):
    """Handles editing an existing stream."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        # Retrieve form data
        stream_name = request.form.get('stream_name')
        description = request.form.get('description')
        room_id = request.form.get('room') or None
        teacher_id = request.form.get('teacher_id') or None

        try:
            # Fetch current stream info
            cursor.execute("SELECT * FROM stream WHERE stream_id = %s", (stream_id,))
            stream_data = cursor.fetchone()

            if not stream_data:
                flash("Stream not found.", "danger")
                return redirect(url_for('streams_blueprint.streams'))

            class_id = stream_data['class_id']

            # Input validation
            if not stream_name:
                flash("Stream name is required!", "warning")
                return redirect(url_for('streams_blueprint.edit_stream', stream_id=stream_id))

            # Check for duplicate stream name in the same class
            cursor.execute("""
                SELECT 1 FROM stream
                WHERE stream_name = %s AND class_id = %s AND stream_id != %s
            """, (stream_name, class_id, stream_id))
            if cursor.fetchone():
                flash("A stream with this name already exists in the class!", "warning")
                return redirect(url_for('streams_blueprint.edit_stream', stream_id=stream_id))

            # Check room assignment conflict (ignore if room is same as current)
            if room_id:
                cursor.execute("""
                    SELECT 1 FROM room_assignment
                    WHERE room_id = %s AND NOT (assigned_to_type = 'stream' AND assigned_to_id = %s)
                """, (room_id, stream_id))
                if cursor.fetchone():
                    flash("The selected room is already assigned!", "warning")
                    return redirect(url_for('streams_blueprint.edit_stream', stream_id=stream_id))

            # Update stream record
            cursor.execute("""
                UPDATE stream
                SET stream_name = %s, description = %s, room_id = %s, teacher_id = %s
                WHERE stream_id = %s
            """, (stream_name, description, room_id, teacher_id, stream_id))
            connection.commit()

            # Update or insert room assignment
            if room_id:
                cursor.execute("""
                    SELECT 1 FROM room_assignment
                    WHERE assigned_to_type = 'stream' AND assigned_to_id = %s
                """, (stream_id,))
                exists = cursor.fetchone()

                if exists:
                    cursor.execute("""
                        UPDATE room_assignment
                        SET room_id = %s
                        WHERE assigned_to_type = 'stream' AND assigned_to_id = %s
                    """, (room_id, stream_id))
                else:
                    now = get_kampala_time()
                    user_id = session.get('id')
                    cursor.execute("""
                        INSERT INTO room_assignment
                        (room_id, user_id, assigned_to_type, assigned_to_id, created_at, updated_at)
                        VALUES (%s, %s, 'stream', %s, %s, %s)
                    """, (room_id, user_id, stream_id, now, now))

                connection.commit()

            flash("Stream updated successfully!", "success")

        except Exception as e:
            connection.rollback()
            flash(f"An error occurred: {str(e)}", "danger")

        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('streams_blueprint.streams'))

    else:
        # GET method: load stream details and options
        cursor.execute("""
            SELECT s.*, c.class_name, c.year, u.username AS teacher_in_charge, r.room_name
            FROM stream s
            JOIN classes c ON s.class_id = c.class_id
            LEFT JOIN users u ON s.teacher_id = u.id
            LEFT JOIN rooms r ON s.room_id = r.room_id
            WHERE s.stream_id = %s
        """, (stream_id,))
        stream_data = cursor.fetchone()

        if not stream_data:
            flash("Stream not found.", "danger")
            cursor.close()
            connection.close()
            return redirect(url_for('streams_blueprint.streams'))

        # Fetch rooms
        cursor.execute("SELECT room_id, room_name FROM rooms")
        rooms = cursor.fetchall()

        # Fetch teachers
        cursor.execute("SELECT id, username FROM users WHERE role = 'teacher'")
        teachers = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template(
            'streams/edit_streams.html',
            stream=stream_data,
            rooms=rooms,
            teachers=teachers,
            segment='streams'
        )







@blueprint.route('/delete_stream/<int:stream_id>', methods=['GET'])
def delete_stream(stream_id):
    """Deletes a stream from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the stream with the given ID
        cursor.execute('DELETE FROM stream WHERE stream_id = %s', (stream_id,))
        connection.commit()
        flash("Stream deleted successfully.", "success")
    except Exception as e:
        flash(f"Error while deleting stream: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('streams_blueprint.streams'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("streams/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'streams'

        return segment

    except:
        return None