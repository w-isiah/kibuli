from flask import render_template, request, redirect, url_for, flash, session
from apps.dep_restock import blueprint
from mysql.connector import Error
from apps import get_db_connection
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import random
import re
from jinja2 import TemplateNotFound







@blueprint.route('/dep_restock')
def dep_restock():
    """Renders the 'products' restock page with category access control."""
    
    if 'id' not in session:
        flash("Please log in to view this page.", "warning")
        return redirect(url_for('authentication_blueprint.login'))

    user_id = session['id']
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute('''
            SELECT 
                p.*, 
                p.name AS product_name,
                c.name AS category_name, 
                (p.quantity * p.price) AS total_price
            FROM product_list p
            JOIN category_list c ON p.category_id = c.CategoryID
            JOIN category_roles cr ON cr.category_id = p.category_id
            WHERE cr.user_id = %s
            ORDER BY p.name
        ''', (user_id,))
        
        products = cursor.fetchall()

    except Error as e:
        logging.exception("Database error while fetching products for restock.")
        flash("An error occurred while fetching products.", "error")
        return render_template('home/page-500.html'), 500

    finally:
        cursor.close()
        connection.close()

    return render_template(
        'dep_restock/p_restock.html',
        products=products,
        segment='p_restock'
    )


















@blueprint.route('/dep_restock_item', methods=['GET', 'POST'])
def dep_restock_item():
    if 'id' not in session:
        flash("You must be logged in to restock products.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    user_id = session['id']
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        sku = request.form.get('sku')
        restock_quantity = int(request.form.get('restock_quantity'))

        # Fetch product if it exists AND the user is authorized via category_roles
        cursor.execute('''
            SELECT p.*
            FROM product_list p
            JOIN category_roles cr ON p.category_id = cr.category_id
            WHERE p.sku = %s AND cr.user_id = %s
        ''', (sku, user_id))

        product = cursor.fetchone()

        if product:
            new_quantity = product['quantity'] + restock_quantity
            cursor.execute('UPDATE product_list SET quantity = %s WHERE sku = %s', (new_quantity, sku))

            # Log restock
            cursor.execute('''
                INSERT INTO inventory_logs (product_id, quantity_change, reason, log_date, user_id)
                VALUES (%s, %s, 'restock', NOW(), %s)
            ''', (product['ProductID'], restock_quantity, user_id))

            connection.commit()
            flash(f"Product with SKU {sku} has been restocked. New quantity: {new_quantity}.", "success")
        else:
            flash(f"Product with SKU {sku} not found or you do not have permission to restock it.", "danger")

    # Fetch only products in categories assigned to this user
    cursor.execute('''
        SELECT p.*
        FROM product_list p
        JOIN category_roles cr ON p.category_id = cr.category_id
        WHERE cr.user_id = %s
        ORDER BY p.name
    ''', (user_id,))
    products = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('dep_restock/p_restock.html', segment='p_restock', products=products)







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
