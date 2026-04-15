from flask import render_template, request, redirect, url_for, flash, session
from apps.p_restock import blueprint
from mysql.connector import Error
from apps import get_db_connection
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import random
import re
from jinja2 import TemplateNotFound


# Route for the 'products' restock page
@blueprint.route('/p_restock')
def p_restock():
    """Renders the 'products' restock page with category and sub-category info."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute('''
            SELECT 
                p.*, 
                p.name AS product_name,
                c.name AS category_name, 
                sc.name AS sub_category_name,
                (p.quantity * p.price) AS total_price
            FROM product_list p
            JOIN sub_category sc ON p.sub_category_id = sc.sub_category_id
            JOIN category_list c ON sc.category_id = c.CategoryID
            ORDER BY p.name
        ''')
        products = cursor.fetchall()

    except Error as e:
        logging.exception("Database error while fetching products for restock.")
        flash("An error occurred while fetching products.", "error")
        return render_template('home/page-500.html'), 500

    finally:
        cursor.close()
        connection.close()

    return render_template(
        'p_restock/p_restock.html',
        products=products,
        segment='p_restock'
    )











# Route to restock product
@blueprint.route('/restock_item', methods=['GET', 'POST'])
def restock_item():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        # Ensure the user is logged in
        if 'id' not in session:
            flash("You must be logged in to restock products.", "danger")
            return redirect(url_for('authentication_blueprint.login'))  # Redirect to login if not logged in

        # Retrieve form data
        sku = request.form.get('sku')
        restock_quantity = int(request.form.get('restock_quantity'))
        user_id = session['id']

        # Check if the product exists
        cursor.execute('SELECT * FROM product_list WHERE sku = %s', (sku,))
        product = cursor.fetchone()

        if product:
            # Update the product's quantity
            new_quantity = product['quantity'] + restock_quantity
            cursor.execute('UPDATE product_list SET quantity = %s WHERE sku = %s', (new_quantity, sku))
            connection.commit()

            # Log the inventory change (restock) with user_id
            cursor.execute("""
                INSERT INTO inventory_logs (product_id, quantity_change, reason, log_date, user_id)
                VALUES (%s, %s, %s, NOW(), %s)
            """, (product['ProductID'], restock_quantity, 'restock', user_id))
            connection.commit()

            # Flash a success message
            flash(f"Product with SKU {sku} has been restocked successfully. New quantity: {new_quantity}.")
        else:
            flash(f"Product with SKU {sku} does not exist!")

    # Fetch the list of products to display in the template
    cursor.execute('SELECT * FROM product_list')
    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('p_restock/p_restock.html', segment='p_restock', products=products)







# Route to handle template rendering
@blueprint.route('/<template>')
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file from app/templates/home/FILE.html
        return render_template(f"home/{template}", segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except Exception as e:
        logging.error(f"Error rendering template: {e}")
        return render_template('home/page-500.html'), 500


# Helper function to extract the current page name from request
def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        return segment if segment else 'p_restock'
    except Exception as e:
        logging.error(f"Error extracting segment: {e}")
        return None