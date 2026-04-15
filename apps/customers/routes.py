from apps.customers import blueprint
from flask import render_template, request, redirect, url_for, flash, session
from flask import Flask
import mysql.connector
from werkzeug.utils import secure_filename
from mysql.connector import Error
from datetime import datetime
import os
import random
import logging
from apps import get_db_connection


# Customer handling route
@blueprint.route('/customers')
def customers():
    # Establish database connection and retrieve customer data
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('SELECT * FROM customer_list')
    customer_data = cursor.fetchall()

    # Close cursor and connection after the query
    cursor.close()
    connection.close()

    # Check user role from session and render appropriate template
    role = session.get('role')
    template = 'customers/customers.html' if role != 'other' else 'o_customers/customers.html'

    # Return the rendered template with customer data
    return render_template(template, customer=customer_data, segment='customers')







@blueprint.route('/add_customer', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        # Get the form data
        name = request.form.get('customer_name')
        contact = request.form.get('contact')
        address = request.form.get('address')
        
        # Ensure the form data is filled
        if not name:
            flash("Please fill out the form!", 'danger')
            return render_template('customers/add_customer.html', segment='add_customer')

        # Check if customer already exists
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute('SELECT * FROM customer_list WHERE name = %s', (name,))
            customer = cursor.fetchone()

            if customer:
                flash("Receiver already exists!", 'warning')
            else:
                # Insert the new customer
                cursor.execute('INSERT INTO customer_list (name, contact, address) VALUES (%s, %s, %s)', 
                               (name, contact, address))
                connection.commit()
                flash("You have successfully registered a Receiver!", 'success')
        except Exception as e:
            flash(f"An error occurred while processing your request: {e}", 'danger')
        finally:
            cursor.close()
            connection.close()
        # Check user role from session and render appropriate template
        role = session.get('role')
        template = 'customers/add_customer.html' if role != 'other' else 'o_customers/add_customer.html'

        return render_template(template, segment='add_customer')
    
    # Handle GET request (render form page)
    # Check user role from session and render appropriate template
    role = session.get('role')
    template = 'customers/add_customer.html' if role != 'other' else 'o_customers/add_customer.html'
    return render_template(template, segment='add_customer')









@blueprint.route('/edit_customer/<int:customer_id>', methods=['POST', 'GET'])
def edit_customer(customer_id):
    if request.method == 'POST':
        # Get data from the form
        name = request.form['name']
        contact = request.form['contact']
        address = request.form['address']
        loyaltypoints = request.form.get('loyaltypoints')  # Optional field, may be NULL

        try:
            # Create connection and execute the update query
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE customer_list 
                SET name=%s, contact=%s, address=%s, loyaltypoints=%s 
                WHERE CustomerID=%s
            """, (name, contact, address, loyaltypoints, customer_id))
            connection.commit()
            
            # Flash success message
            flash("Reciever Data Updated Successfully", "success")
        except Exception as e:
            # Flash error message if any exception occurs
            flash(f"Error: {str(e)}", "danger")
        finally:
            # Close the cursor and connection
            cursor.close()
            connection.close()
            return redirect(url_for('customers_blueprint.customers'))

    elif request.method == 'GET':
        # Retrieve customer data to pre-fill the form (if needed)
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM customer_list WHERE CustomerID = %s", (customer_id,))
        customer = cursor.fetchone()
        cursor.close()
        connection.close()
        
        # If customer exists, render an edit form
        if customer:
            # Check user role from session and render appropriate template
            role = session.get('role')
            template = 'customers/edit_customer.html' if role != 'other' else 'o_customers/edit_customer.html'
            return render_template(template, customer=customer)
        else:
            flash("Reciever not found.", "danger")
            return redirect(url_for('customers_blueprint.customers'))









@blueprint.route('/delete_customer/<string:get_id>')
def delete_customer(get_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Using a parameterized query to prevent SQL injection
        cursor.execute('DELETE FROM customer_list WHERE CustomerID = %s', (get_id,))

        # Commit the transaction to apply the changes
        connection.commit()

        # Check if any row was affected (i.e., the customer existed and was deleted)
        if cursor.rowcount > 0:
            flash("Receiver has been successfully deleted.", 'success')
        else:
            flash("Receiver not found or already deleted.", 'warning')
    except Exception as e:
        flash(f"An error occurred while trying to delete the receiver: {e}", 'danger')
    finally:
        # Close the cursor and connection
        cursor.close()
        connection.close()

    # Redirect to the 'manage_customer' route
    return redirect(url_for('customers_blueprint.customers'))



    







# Dynamic route for rendering other templates
@blueprint.route('/<template>')
def route_template(template):
    try:
        # Ensure the template ends with '.html'
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        flash("The requested page was not found.", "danger")
        return render_template('home/page-404.html'), 404

    except Exception as e:
        flash("An unexpected error occurred. Please try again later.", "danger")
        return render_template('home/page-500.html'), 500


def get_segment(request):
    """Extracts the last part of the URL path to identify the current page."""
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'customers'
        return segment

    except Exception as e:
        return None
