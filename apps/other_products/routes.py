import os
import random
import logging
from flask import render_template, request, redirect, url_for, flash,jsonify,current_app,session
from werkzeug.utils import secure_filename
from mysql.connector import Error
from apps import get_db_connection
from apps.other_products import blueprint
import mysql.connector
from datetime import datetime 


# Helper function to calculate formatted totals
def calculate_formatted_totals(products):
    total_sum = sum(product['total_price'] for product in products)
    total_price = sum(product['price'] for product in products)

    formatted_total_sum = "{:,.2f}".format(total_sum) if total_sum else '0.00'
    formatted_total_price = "{:,.2f}".format(total_price) if total_price else '0.00'

    for product in products:
        product['formatted_total_price'] = "{:,.2f}".format(product['total_price']) if product['total_price'] else '0.00'
        product['formatted_price'] = "{:,.2f}".format(product['price']) if product['price'] else '0.00'

    return formatted_total_sum, formatted_total_price


# Access the upload folder from the current Flask app configuration
def allowed_file(filename):
    """Check if the uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']







@blueprint.route('/o_products')
def o_products():
    """Renders products page showing only those in sub-categories assigned to the logged-in user."""
    try:
        user_id = session.get('id') 
        if not user_id:
            flash("Please log in to view products.", "warning")
            return render_template('auth/login.html')

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get filter values
        sku = request.args.get('sku', '').strip()
        unique_number = request.args.get('unique_number', '').strip()
        name = request.args.get('name', '').strip()
        category = request.args.get('category', '').strip()
        sub_category_id = request.args.get('sub_category_id', '').strip()

        # Base query
        query = '''
            SELECT 
                p.*, 
                c.name AS category_name,
                COALESCE(sc.name, 'None') AS sub_category_name
            FROM product_list p
            INNER JOIN category_list c ON p.category_id = c.CategoryID
            LEFT JOIN sub_category sc ON p.sub_category_id = sc.sub_category_id
            INNER JOIN other_roles orl ON orl.sub_category_id = p.sub_category_id
            WHERE orl.user_id = %(user_id)s
        '''

        filters = []
        params = {"user_id": user_id}

        if sku:
            filters.append("p.sku LIKE %(sku)s")
            params["sku"] = f"%{sku}%"
        if unique_number:
            filters.append("p.unique_number LIKE %(unique_number)s")
            params["unique_number"] = f"%{unique_number}%"
        if name:
            filters.append("p.name LIKE %(name)s")
            params["name"] = f"%{name}%"
        if category:
            filters.append("c.name = %(category)s")
            params["category"] = category
        if sub_category_id:
            filters.append("sc.sub_category_id = %(sub_category_id)s")
            params["sub_category_id"] = sub_category_id

        if filters:
            query += " AND " + " AND ".join(filters)

        query += " ORDER BY p.name"

        # Execute query
        cursor.execute(query, params)
        products = cursor.fetchall()

        # Load all categories for filters
        cursor.execute("SELECT name FROM category_list ORDER BY name")
        categories = [row['name'] for row in cursor.fetchall()]

        # Load sub-categories for dynamic filter dropdown
        cursor.execute('''
            SELECT DISTINCT
                sc.sub_category_id,
                sc.name AS sub_category_name,
                c.name AS category_name
            FROM other_roles orl
            INNER JOIN sub_category sc ON orl.sub_category_id = sc.sub_category_id
            INNER JOIN category_list c ON sc.category_id = c.CategoryID
            WHERE orl.user_id = %s
            ORDER BY c.name, sc.name
        ''', (user_id,))
        sub_categories = cursor.fetchall()


    except Error as e:
        logging.error(f"Database error while fetching filtered products: {e}")
        flash("An error occurred while loading your products.", "error")
        return render_template('products/page-500.html'), 500

    finally:
        if cursor: cursor.close()
        if connection: connection.close()

    return render_template(
        'other_products/products.html',
        products=products,
        categories=categories,
        sub_categories=sub_categories,
        selected_filters={
            'sku': sku,
            'unique_number': unique_number,
            'name': name,
            'category': category,
            'sub_category_id': sub_category_id
        },
        segment='products'
    )






























@blueprint.route('/sub_category_data')
def sub_category_data():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)  # Ensure dictionary cursor
        cursor.execute('''
            SELECT 
                sc.sub_category_id,
                sc.name AS sub_category_name,
                sc.description AS sub_category_description,
                c.CategoryID AS category_id,
                c.name AS category_name,
                c.Description AS category_description
            FROM sub_category sc
            JOIN category_list c ON sc.category_id = c.CategoryID
            ORDER BY sc.name
        ''')
        sub_categories_data = cursor.fetchall()
        return jsonify(sub_categories_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
















@blueprint.route('/subc_data', methods=['GET'])
def subc_data():
    category_id = request.args.get('category_id')  # Get category_id from query params
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Fetch sub-categories matching the category_id
    cursor.execute('SELECT * FROM sub_category WHERE category_id = %s ORDER BY name', (category_id,))
    sub_categories = cursor.fetchall()
    
    connection.close()
    return jsonify(sub_categories)























@blueprint.route('/<template>')
def route_template(template):
    try:
        # Ensure the template ends with '.html' for correct render
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        return render_template("products/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('products/page-404.html'), 404

    except Exception as e:
        return render_template('products/page-500.html'), 500


def get_segment(request):
    """Extracts the last part of the URL path to identify the current page."""
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'products'
        return segment

    except Exception as e:
        return None
