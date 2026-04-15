from apps.term import blueprint
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


from flask import request, render_template, flash
from datetime import datetime
import pytz, json


def get_kampala_time():
    """Returns the current datetime in the Africa/Kampala timezone."""
    return datetime.now(pytz.timezone("Africa/Kampala"))

@blueprint.route('/term')
def term():
    """Display all terms with their academic years."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Get all terms with academic year names
        cursor.execute('''
            SELECT t.*, y.year_name 
            FROM terms t
            LEFT JOIN study_year y ON t.year_id = y.year_id
            ORDER BY t.start_on DESC
        ''')
        terms = cursor.fetchall()
        
        return render_template('term/term.html', terms=terms, segment='term')
        
    except Exception as e:
        flash(f"Error loading terms: {str(e)}", "danger")
        return redirect(url_for('home_blueprint.index'))
        
    finally:
        cursor.close()
        connection.close()









from flask import request, flash, redirect, url_for, render_template, session
import json
from datetime import datetime
import pytz

@blueprint.route('/add_term', methods=['GET', 'POST'])
def add_term():
    """Handles adding a new term with comprehensive validation and audit logging."""
    
    def get_kampala_time():
        """Get current time in Kampala timezone."""
        return datetime.now(pytz.timezone("Africa/Kampala"))
    
    def get_current_user():
        """Get current logged-in user."""
        return session.get('username', 'system')  # Adjust based on your session

    # GET request - Display the add term form
    if request.method == 'GET':
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        try:
            # Fetch all academic years for dropdown
            cursor.execute('SELECT year_id, year_name FROM study_year ORDER BY year_name DESC')
            study_years = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            return render_template('term/add_term.html', 
                                 study_years=study_years, 
                                 segment='add_term')
                                 
        except Exception as e:
            flash(f"Error loading academic years: {str(e)}", "danger")
            if cursor:
                cursor.close()
            if connection:
                connection.close()
            return redirect(url_for('term_blueprint.term'))
    
    # POST request - Process form submission
    elif request.method == 'POST':
        # Get and sanitize form data
        term_name = request.form.get('term_name', '').strip()
        start_on = request.form.get('start_on', '').strip()
        ends_on = request.form.get('ends_on', '').strip()
        year_id = request.form.get('year_id', '').strip()
        status = request.form.get('status', 'inactive')  # Default based on your schema
        
        # Convert numeric status to string if needed
        if status == '1':
            status = 'active'
        elif status == '0':
            status = 'inactive'
        
        # Debug logging (remove in production)
        print(f"Adding term: name={term_name}, start={start_on}, end={ends_on}, year={year_id}, status={status}")
        
        # Comprehensive validation
        validation_errors = []
        
        # Required field validation
        if not term_name:
            validation_errors.append("Term name is required!")
        
        if not start_on:
            validation_errors.append("Start date is required!")
        
        if not ends_on:
            validation_errors.append("End date is required!")
        
        if not year_id:
            validation_errors.append("Academic year is required!")
        
        # Term name length validation
        if term_name and len(term_name) > 20:
            validation_errors.append("Term name must not exceed 20 characters!")
        
        # Date validation
        if start_on and ends_on:
            try:
                start_date = datetime.strptime(start_on, '%Y-%m-%d')
                end_date = datetime.strptime(ends_on, '%Y-%m-%d')
                
                if end_date < start_date:
                    validation_errors.append("End date cannot be earlier than start date!")
                
                # Optional: Check if start date is in the past
                today = datetime.now().date()
                if start_date.date() < today:
                    flash("Note: Start date is in the past.", "info")
                    
            except ValueError:
                validation_errors.append("Invalid date format! Please use YYYY-MM-DD format.")
        
        # If there are validation errors, show them and redirect
        if validation_errors:
            for error in validation_errors:
                flash(error, "danger")
            return redirect(url_for('term_blueprint.add_term'))

        connection = None
        cursor = None
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            # Check for duplicate term name in the same academic year
            cursor.execute('''
                SELECT term_id, term_name 
                FROM terms 
                WHERE term_name = %s AND year_id = %s
            ''', (term_name, year_id))
            
            existing_term = cursor.fetchone()
            if existing_term:
                flash(f"A term named '{term_name}' already exists for this academic year (ID: {existing_term['term_id']})!", "warning")
                return redirect(url_for('term_blueprint.add_term'))
            
            # Check for date overlaps with existing terms in the same academic year
            cursor.execute('''
                SELECT term_id, term_name 
                FROM terms 
                WHERE year_id = %s 
                AND (
                    (start_on <= %s AND ends_on >= %s) OR  -- New term starts within existing
                    (start_on <= %s AND ends_on >= %s) OR  -- New term ends within existing
                    (start_on >= %s AND ends_on <= %s)     -- New term completely within existing
                )
            ''', (year_id, start_on, start_on, ends_on, ends_on, start_on, ends_on))
            
            overlapping_terms = cursor.fetchall()
            if overlapping_terms:
                term_list = ', '.join([f"{t['term_name']} (ID: {t['term_id']})" for t in overlapping_terms])
                flash(f"Term dates overlap with existing term(s): {term_list}", "warning")
                return redirect(url_for('term_blueprint.add_term'))
            
            # Get current timestamp
            current_time = get_kampala_time()
            
            # Insert the new term
            cursor.execute('''
                INSERT INTO terms (term_name, start_on, ends_on, year_id, status, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (term_name, start_on, ends_on, year_id, status, current_time))
            
            term_id = cursor.lastrowid
            
            if not term_id:
                flash("Failed to create term. Please try again.", "danger")
                connection.rollback()
                return redirect(url_for('term_blueprint.add_term'))
            
            connection.commit()
            
            # Prepare data for audit logging
            new_value = {
                'term_id': term_id,
                'term_name': term_name,
                'start_on': start_on,
                'ends_on': ends_on,
                'year_id': int(year_id) if year_id else None,
                'status': status,
                'updated_at': str(current_time)
            }
            
            # Insert audit log entry
            cursor.execute('''
                INSERT INTO term_logs (
                    term_id, 
                    action, 
                    changed_by, 
                    change_time, 
                    old_value, 
                    new_value, 
                    notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                term_id,
                'CREATE',
                get_current_user(),
                current_time,
                None,  # No old value for create action
                json.dumps(new_value, indent=2),
                f"Term '{term_name}' created by {get_current_user()}"
            ))
            
            connection.commit()
            
            flash(f"Term '{term_name}' created successfully!", "success")
            
            # Redirect to terms list
            return redirect(url_for('term_blueprint.term'))
            
        except Exception as e:
            if connection:
                connection.rollback()
            flash(f"An error occurred while creating the term: {str(e)}", "danger")
            print(f"Error in add_term: {str(e)}")  # Log for debugging
            return redirect(url_for('term_blueprint.add_term'))
            
        finally:
            # Ensure resources are cleaned up
            if cursor:
                cursor.close()
            if connection:
                connection.close()

















from flask import request, flash, redirect, url_for, render_template, session
import json
from datetime import datetime
import pytz

@blueprint.route('/edit_term/<int:term_id>', methods=['GET', 'POST'])
def edit_term(term_id):
    """Handles editing an existing term and logs the changes."""
    
    def get_kampala_time():
        return datetime.now(pytz.timezone("Africa/Kampala"))
    
    def get_current_user():
        # Replace with your actual current user retrieval logic
        return session.get('username', 'system')  # Or your user session key

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # GET request - Show edit form
    if request.method == 'GET':
        try:
            # Fetch term data
            cursor.execute("SELECT * FROM terms WHERE term_id = %s", (term_id,))
            term_data = cursor.fetchone()

            if not term_data:
                flash("Term not found.", "danger")
                cursor.close()
                connection.close()
                return redirect(url_for('term_blueprint.term'))

            # Fetch available academic years for dropdown
            cursor.execute("SELECT year_id, year_name FROM study_year ORDER BY year_name DESC")
            years = cursor.fetchall()
            
            cursor.close()
            connection.close()

            return render_template('term/edit_term.html', 
                                 term=term_data, 
                                 years=years, 
                                 segment='term')

        except Exception as e:
            flash(f"Error loading term data: {str(e)}", "danger")
            cursor.close()
            connection.close()
            return redirect(url_for('term_blueprint.term'))

    # POST request - Process form submission
    elif request.method == 'POST':
        try:
            # Get form data
            term_name = request.form.get('term_name', '').strip()
            start_on = request.form.get('start_on', '').strip()
            ends_on = request.form.get('ends_on', '').strip()
            year_id = request.form.get('year_id', '').strip()
            status = request.form.get('status', 'inactive')  # Default to 'inactive' based on your schema
            
            # Convert status to your database format
            if status == '1':
                status = 'active'
            elif status == '0':
                status = 'inactive'
            # If form sends 'active'/'inactive' directly, leave as is
            
            # Debug print (remove in production)
            print(f'Term: {term_name}, Start: {start_on}, End: {ends_on}, Year: {year_id}, Status: {status}')

            # Validate required fields
            validation_errors = []
            
            if not term_name:
                validation_errors.append("Term name is required!")
            
            if not start_on:
                validation_errors.append("Start date is required!")
            
            if not ends_on:
                validation_errors.append("End date is required!")
            
            if not year_id:
                validation_errors.append("Academic year is required!")
            
            if validation_errors:
                for error in validation_errors:
                    flash(error, "danger")
                return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

            # Validate term name length
            if len(term_name) > 20:
                flash("Term name must be 20 characters or fewer!", "danger")
                return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

            # Validate dates
            try:
                start_date = datetime.strptime(start_on, '%Y-%m-%d')
                end_date = datetime.strptime(ends_on, '%Y-%m-%d')
                
                if end_date < start_date:
                    flash("End date cannot be earlier than start date!", "danger")
                    return redirect(url_for('term_blueprint.edit_term', term_id=term_id))
                    
            except ValueError:
                flash("Invalid date format! Please use YYYY-MM-DD format.", "danger")
                return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

            # Fetch old term data for logging
            cursor.execute("SELECT * FROM terms WHERE term_id = %s", (term_id,))
            old_term = cursor.fetchone()

            if not old_term:
                flash("Term not found.", "danger")
                return redirect(url_for('term_blueprint.term'))

            # Check for duplicate term name in the same academic year (excluding current term)
            cursor.execute("""
                SELECT term_id, term_name FROM terms
                WHERE term_name = %s 
                AND year_id = %s 
                AND term_id != %s
            """, (term_name, year_id, term_id))
            
            duplicate_term = cursor.fetchone()
            if duplicate_term:
                flash(f"A term named '{term_name}' already exists for the selected academic year (Term ID: {duplicate_term['term_id']})!", "warning")
                return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

            # Check for date overlaps with other terms in same year (excluding current term)
            cursor.execute("""
                SELECT term_id, term_name FROM terms
                WHERE year_id = %s 
                AND term_id != %s
                AND status = 'active'
                AND (
                    (start_on <= %s AND ends_on >= %s) OR   -- New term starts within existing term
                    (start_on <= %s AND ends_on >= %s) OR   -- New term ends within existing term
                    (start_on >= %s AND ends_on <= %s)      -- New term completely within existing term
                )
            """, (year_id, term_id, start_on, start_on, ends_on, ends_on, start_on, ends_on))
            
            overlapping_terms = cursor.fetchall()
            if overlapping_terms:
                term_names = ', '.join([f"{t['term_name']} (ID: {t['term_id']})" for t in overlapping_terms])
                flash(f"Term dates overlap with active term(s): {term_names}", "warning")
                return redirect(url_for('term_blueprint.edit_term', term_id=term_id))

            # Get current timestamp for updated_at
            current_time = get_kampala_time()
            
            # Update the term with updated_at timestamp
            cursor.execute("""
                UPDATE terms
                SET term_name = %s, 
                    start_on = %s, 
                    ends_on = %s, 
                    year_id = %s, 
                    status = %s,
                    updated_at = %s
                WHERE term_id = %s
            """, (term_name, start_on, ends_on, year_id, status, current_time, term_id))
            
            if cursor.rowcount == 0:
                flash("No changes made or term not found.", "info")
                connection.rollback()
                cursor.close()
                connection.close()
                return redirect(url_for('term_blueprint.term'))

            connection.commit()

            # Prepare old and new values for logging
            old_value = json.dumps(old_term, default=str, indent=2)
            new_value = json.dumps({
                "term_id": term_id,
                "term_name": term_name,
                "start_on": start_on,
                "ends_on": ends_on,
                "year_id": int(year_id) if year_id else None,
                "status": status,
                "updated_at": str(current_time)
            }, default=str, indent=2)

            # Insert audit log entry
            cursor.execute("""
                INSERT INTO term_logs (
                    term_id, 
                    action, 
                    changed_by, 
                    change_time, 
                    old_value, 
                    new_value, 
                    notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                term_id,
                "UPDATE",
                get_current_user(),
                current_time,
                old_value,
                new_value,
                f"Term '{term_name}' (ID: {term_id}) updated by {get_current_user()}"
            ))
            
            connection.commit()

            flash(f"Term '{term_name}' updated successfully!", "success")

        except Exception as e:
            connection.rollback()
            flash(f"An error occurred while updating the term: {str(e)}", "danger")
            print(f"Error in edit_term: {str(e)}")  # Log for debugging
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('term_blueprint.term'))




















@blueprint.route('/delete_term/<int:term_id>')
def delete_term(term_id):
    """Deletes a term and logs the action."""
    # Check if user has permission (only super_admin can delete)
    if session.get('role') != 'super_admin':
        flash("You do not have permission to delete terms.", "danger")
        return redirect(url_for('term_blueprint.term'))
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Check if term exists
        cursor.execute("SELECT * FROM terms WHERE term_id = %s", (term_id,))
        term = cursor.fetchone()

        if not term:
            flash("Term not found.", "warning")
            return redirect(url_for('term_blueprint.term'))

        # Check if term is being used elsewhere (optional)
        # cursor.execute("SELECT COUNT(*) as count FROM some_other_table WHERE term_id = %s", (term_id,))
        # if cursor.fetchone()['count'] > 0:
        #     flash("Cannot delete term. It is being used in other records.", "danger")
        #     return redirect(url_for('term_blueprint.term'))

        term_name = term['term_name']
        
        # Save old value for logging
        old_value_json = json.dumps(term, default=str)

        # Delete the term
        cursor.execute("DELETE FROM terms WHERE term_id = %s", (term_id,))
        
        if cursor.rowcount == 0:
            flash("No term was deleted.", "info")
            return redirect(url_for('term_blueprint.term'))
        
        connection.commit()

        # Log the deletion
        cursor.execute("""
            INSERT INTO term_logs (term_id, action, changed_by, change_time, old_value, new_value, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            term_id,
            'DELETE',
            session.get('username', 'system'),  # Use actual logged-in user
            get_kampala_time(),
            old_value_json,
            None,
            f"Term '{term_name}' was deleted by {session.get('username', 'system')}"
        ))
        connection.commit()

        flash(f"Term '{term_name}' deleted successfully.", "success")

    except Exception as e:
        connection.rollback()
        flash(f"An error occurred while deleting the term: {str(e)}", "danger")
        print(f"Error deleting term {term_id}: {str(e)}")  # Log for debugging

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('term_blueprint.term'))









@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("term/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'term'

        return segment

    except:
        return None
