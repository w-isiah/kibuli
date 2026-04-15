# Assuming your blueprint is defined in an 'apps.suppliers' module 
# and aliased to 'blueprint'
from apps.suppliers import blueprint # Renamed import alias

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

# Assuming 'blueprint' is imported as 'suppliers_blueprint'
# from apps.suppliers import blueprint as suppliers_blueprint 
# If the above import is not possible, ensure 'blueprint' is correctly imported and aliased.

# LIST SUPPLIERS
@blueprint.route('/suppliers') # Using the conventional alias
def suppliers():
    """Fetches all suppliers and renders the manage suppliers page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Fetch all suppliers from the Suppliers table
        cursor.execute('SELECT * FROM Suppliers ORDER BY Name ASC') 
        suppliers_list = cursor.fetchall()
        
    except Error as e:
        # Log the error and notify the user
        logging.error(f"Database error fetching suppliers: {e}")
        flash("Could not fetch suppliers due to a database error.", "danger")
        suppliers_list = []
        
    finally:
        # Ensure resources are closed
        cursor.close()
        connection.close()

    # Renders the template specific to suppliers
    return render_template('suppliers/suppliers.html', suppliers=suppliers_list, segment='suppliers')










# ADD SUPPLIER
@blueprint.route('/add_supplier', methods=['GET', 'POST']) # Updated blueprint and route
def add_supplier():
    """Handles the adding of a new supplier."""
    if request.method == 'POST':
        # Capture form data
        supplier_name = request.form.get('name') 
        contact_details = request.form.get('contact_details') # New field
        supplier_type = request.form.get('type')             # New field

        # Validate input (Name is mandatory)
        if not supplier_name:
            flash("Supplier Name is required!", "warning")
        elif not re.match(r'^[A-Za-z0-9_ ]+$', supplier_name):
            flash('Supplier name must contain only letters and numbers!', "danger")
        else:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            try:
                # Check if the supplier already exists by Name
                cursor.execute('SELECT * FROM Suppliers WHERE Name = %s', (supplier_name,))
                existing_supplier = cursor.fetchone()

                if existing_supplier:
                    flash("Supplier already exists!", "warning")
                else:
                    # Insert the new supplier into the Suppliers table
                    cursor.execute(
                        'INSERT INTO Suppliers (Name, ContactDetails, Type) VALUES (%s, %s, %s)', 
                        (supplier_name, contact_details, supplier_type)
                    )
                    connection.commit()
                    flash("Supplier successfully added!", "success")

            except mysql.connector.Error as err:
                flash(f"Database Error: {err}", "danger")
            except Exception as e:
                flash(f"An unexpected error occurred: {e}", "danger")
            finally:
                cursor.close()
                connection.close()
    
    # Pass 'suppliers' segment for navigation highlighting
    return render_template('suppliers/add_supplier.html', segment='add_supplier')





# ---

# EDIT SUPPLIER
@blueprint.route('/edit_supplier/<int:supplier_id>', methods=['GET', 'POST']) # Updated blueprint and route
def edit_supplier(supplier_id):
    """Handles editing an existing supplier."""
    if request.method == 'POST':
        # Capture form data
        supplier_name = request.form['name']
        contact_details = request.form.get('contact_details')
        supplier_type = request.form.get('type')
        
        # Validation for POST request (similar to add_supplier)
        if not supplier_name or not re.match(r'^[A-Za-z0-9_ ]+$', supplier_name):
             flash('Invalid supplier name provided.', "danger")
             return redirect(url_for('suppliers_blueprint.edit_supplier', supplier_id=supplier_id))
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Update the supplier in the Suppliers table based on SupplierID
            cursor.execute("""
                UPDATE Suppliers
                SET Name = %s, ContactDetails = %s, Type = %s
                WHERE SupplierID = %s
            """, (supplier_name, contact_details, supplier_type, supplier_id))
            connection.commit()

            flash("Supplier updated successfully!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        # Redirect to the suppliers list
        return redirect(url_for('suppliers_blueprint.suppliers'))

    elif request.method == 'GET':
        # Retrieve the supplier to pre-fill the form
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Select from Suppliers table using the SupplierID
        cursor.execute("SELECT SupplierID, Name, ContactDetails, Type FROM Suppliers WHERE SupplierID = %s", (supplier_id,))
        supplier = cursor.fetchone()
        
        cursor.close()
        connection.close()

        if supplier:
            # Pass the retrieved supplier object to the template
            return render_template('suppliers/edit_supplier.html', supplier=supplier, segment='suppliers')
        else:
            flash("Supplier not found.", "danger")
            return redirect(url_for('suppliers_blueprint.suppliers'))

# ---

# DELETE SUPPLIER
@blueprint.route('/delete_supplier/<int:supplier_id>') # Updated blueprint and route
def delete_supplier(supplier_id):
    """Deletes a supplier from the database."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Delete the supplier from the Suppliers table
        cursor.execute('DELETE FROM Suppliers WHERE SupplierID = %s', (supplier_id,))
        connection.commit()
        flash("Supplier deleted successfully.", "success")
        
    except Exception as e:
        # This catch will handle Foreign Key errors if the supplier is linked to assets
        flash(f"Error: Cannot delete supplier. It may be linked to existing assets. ({str(e)})", "danger")
    finally:
        cursor.close()
        connection.close()

    # Redirect to the suppliers list
    return redirect(url_for('suppliers_blueprint.suppliers'))