import os
import random
import logging
from flask import render_template, request, redirect, url_for, flash,jsonify,current_app,session
from werkzeug.utils import secure_filename
from mysql.connector import Error
from apps import get_db_connection
from apps.fixed_assets import blueprint
import mysql.connector
from datetime import datetime 





from flask import Blueprint, render_template, request, flash, current_app
import logging
from mysql.connector import Error
from werkzeug.utils import secure_filename
import os


# --- Allowed image extensions ---
def allowed_file(filename):
    """Check if uploaded file has a valid image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']





@blueprint.route('/fixed_assets')
def fixed_assets():
    """Render the Fixed Assets page with optional filters for department, section, and other fields."""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # --- Filters from query parameters ---
        identification_number = request.args.get('identification_number', '').strip()
        serial_number = request.args.get('serial_number', '').strip()
        description = request.args.get('description', '').strip()
        department_id = request.args.get('department_id', '').strip()
        section_id = request.args.get('section_id', '').strip()
        ownership_status = request.args.get('ownership_status', '').strip()
        asset_condition = request.args.get('asset_condition', '').strip()

        # --- Base Query with joins ---
        query = """
            SELECT 
                fa.*,
                d.name AS department_name,
                s.name AS section_name,
                CONCAT(u.first_name, ' ', u.last_name) AS user_name
            FROM fixed_assets fa
            LEFT JOIN departments d ON fa.department_id = d.department_id
            LEFT JOIN sections s ON fa.section_id = s.section_id
            LEFT JOIN users u ON fa.user_id = u.id
            WHERE 1=1
        """

        # --- Apply filters dynamically ---
        filters = []
        params = {}

        if identification_number:
            filters.append("fa.IdentificationNumber LIKE %(identification_number)s")
            params["identification_number"] = f"%{identification_number}%"
        if serial_number:
            filters.append("fa.SerialNumber LIKE %(serial_number)s")
            params["serial_number"] = f"%{serial_number}%"
        if description:
            filters.append("fa.AssetDescription LIKE %(description)s")
            params["description"] = f"%{description}%"
        if department_id:
            filters.append("fa.department_id = %(department_id)s")
            params["department_id"] = department_id
        if section_id:
            filters.append("fa.section_id = %(section_id)s")
            params["section_id"] = section_id
        if ownership_status:
            filters.append("fa.OwnershipStatus = %(ownership_status)s")
            params["ownership_status"] = ownership_status
        if asset_condition:
            filters.append("fa.AssetCondition = %(asset_condition)s")
            params["asset_condition"] = asset_condition

        if filters:
            query += " AND " + " AND ".join(filters)

        query += " ORDER BY fa.AssetDescription"

        # --- Execute query ---
        cursor.execute(query, params)
        assets = cursor.fetchall()

        # --- Lookup data for dropdowns ---
        cursor.execute("SELECT department_id, name FROM departments ORDER BY name")
        departments = cursor.fetchall()

        cursor.execute("SELECT section_id, name, department_id FROM sections ORDER BY name")
        sections = cursor.fetchall()

        cursor.execute("SELECT id, CONCAT(first_name, ' ', last_name) AS name FROM users ORDER BY first_name, last_name")
        users = cursor.fetchall()  # updated from custodians

    except Error as e:
        logging.error(f"Database error while fetching fixed assets: {e}")
        flash("An error occurred while fetching fixed assets.", "error")
        return render_template('fixed_assets/page-500.html'), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template(
        'fixed_assets/fixed_assets.html',
        assets=assets,
        departments=departments,
        sections=sections,
        users=users,  # updated variable
        selected_filters={
            'identification_number': identification_number,
            'serial_number': serial_number,
            'description': description,
            'department_id': department_id,
            'section_id': section_id,
            'ownership_status': ownership_status,
            'asset_condition': asset_condition
        },
        segment='fixed_assets'
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










@blueprint.route('/add_fixed_asset', methods=['GET', 'POST'])
def add_fixed_asset():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch departments, sections, suppliers, and users
        cursor.execute("SELECT department_id, name FROM departments ORDER BY name")
        departments = cursor.fetchall()

        cursor.execute("SELECT section_id, name, department_id FROM sections ORDER BY name")
        sections = cursor.fetchall()

        cursor.execute("SELECT SupplierID, name FROM suppliers ORDER BY name")
        suppliers = cursor.fetchall()

        cursor.execute("SELECT id, CONCAT(first_name, ' ', last_name) AS name FROM users ORDER BY first_name, last_name")
        users = cursor.fetchall()

        # Generate unique IdentificationNumber
        random_num = random.randint(1005540, 9978799)
        while True:
            cursor.execute("SELECT 1 FROM fixed_assets WHERE IdentificationNumber = %s", (random_num,))
            if not cursor.fetchone():
                break
            random_num = random.randint(1005540, 9978799)

        if request.method == 'POST':
            # Validate required fields
            required_fields = ['description', 'department_id', 'ownership_status', 'asset_condition']
            missing_fields = []
            for field in required_fields:
                if not request.form.get(field):
                    field_name = field.replace('_', ' ').title()
                    missing_fields.append(field_name)
            
            if missing_fields:
                flash(f"❌ Missing required fields: {', '.join(missing_fields)}", "danger")
                return render_template(
                    'fixed_assets/add_fixed_asset.html',
                    departments=departments,
                    sections=sections,
                    suppliers=suppliers,
                    users=users,
                    random_num=random_num,
                    segment='add_fixed_asset'
                )

            # Retrieve and sanitize form values
            identification_number = request.form.get('identification_number') or random_num
            serial_number = request.form.get('serial_number', '').strip()
            serial_number = serial_number if serial_number else None
            description = request.form.get('description', '').strip()
            department_id = request.form.get('department_id')
            section_id = request.form.get('section_id')
            section_id = section_id if section_id else None
            supplier_id = request.form.get('supplier_id')
            supplier_id = supplier_id if supplier_id else None
            user_id = request.form.get('user_id')
            user_id = user_id if user_id else None
            ownership_status = request.form.get('ownership_status')
            asset_condition = request.form.get('asset_condition')

            # Handle image upload
            image_file = request.files.get('image')
            image_filename = None
            if image_file and image_file.filename:
                if allowed_file(image_file.filename):
                    try:
                        filename = secure_filename(image_file.filename)
                        image_filename = f"{identification_number}_{filename}"
                        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'])
                        os.makedirs(upload_folder, exist_ok=True)
                        image_path = os.path.join(upload_folder, image_filename)
                        image_file.save(image_path)
                    except Exception as e:
                        current_app.logger.error(f"Image upload failed: {str(e)}")
                        flash("⚠️ Error saving image file", "warning")
                else:
                    flash("⚠️ Invalid file type. Please upload JPG, PNG, GIF, or WEBP image.", "warning")

            # Insert new asset into database
            cursor.execute('''
                INSERT INTO fixed_assets 
                (IdentificationNumber, SerialNumber, AssetDescription, department_id, section_id,
                 SupplierID, user_id, OwnershipStatus, AssetCondition, image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                identification_number, 
                serial_number, 
                description, 
                department_id, 
                section_id,
                supplier_id, 
                user_id, 
                ownership_status, 
                asset_condition, 
                image_filename
            ))

            # Log the asset creation
            current_user_id = session.get('id')
            if current_user_id:
                cursor.execute('''
                    INSERT INTO asset_logs (asset_id, user_id, action, log_date, remarks)
                    VALUES (%s, %s, %s, NOW(), %s)
                ''', (cursor.lastrowid, current_user_id, 'create', 'New asset created'))

            conn.commit()

            flash("✅ Fixed Asset added successfully!", "success")
            return redirect(url_for('fixed_assets_blueprint.fixed_assets'))

    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Error adding fixed asset: {str(e)}")
        flash(f"❌ Error adding asset: {str(e)}", "danger")

    finally:
        cursor.close()
        conn.close()

    return render_template(
        'fixed_assets/add_fixed_asset.html',
        departments=departments,
        sections=sections,
        suppliers=suppliers,
        users=users,
        random_num=random_num,
        segment='add_fixed_asset'
    )









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





@blueprint.route('/sections_data', methods=['GET'])
def sections_data():
    department_id = request.args.get('department_id')  # Get department_id from query params
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Fetch sections matching the department_id
    cursor.execute('SELECT * FROM sections WHERE department_id = %s ORDER BY name', (department_id,))
    sections = cursor.fetchall()
    
    connection.close()
    return jsonify(sections)











@blueprint.route('/edit_fixed_asset/<int:asset_id>', methods=['GET', 'POST'])
def edit_fixed_asset(asset_id):
    """Edit an existing fixed asset record."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 🎯 1️⃣ Fetch asset details (with department & section names)
        cursor.execute('''
            SELECT fa.*, d.name AS department_name, s.name AS section_name
            FROM fixed_assets fa
            LEFT JOIN departments d ON fa.department_id = d.department_id
            LEFT JOIN sections s ON fa.section_id = s.section_id
            WHERE fa.AssetID = %s
        ''', (asset_id,))
        asset = cursor.fetchone()

        if not asset:
            flash("❌ Asset not found!", "danger")
            return redirect(url_for('fixed_assets_blueprint.fixed_assets'))

        # 🎯 2️⃣ Fetch dropdown data
        cursor.execute('SELECT * FROM departments ORDER BY name')
        departments = cursor.fetchall()

        cursor.execute('SELECT * FROM sections ORDER BY name')
        sections = cursor.fetchall()

        cursor.execute('SELECT id, first_name, last_name FROM users ORDER BY first_name, last_name')
        users = cursor.fetchall()

        # 🎯 3️⃣ Handle POST (form submission)
        if request.method == 'POST':
            identification_number = request.form.get('identification_number')
            serial_number = request.form.get('serial_number')
            description = request.form.get('description')
            department_id = request.form.get('department_id') or None
            section_id = request.form.get('section_id') or None
            user_id_selected = request.form.get('user_id') or None
            ownership_status = request.form.get('ownership_status')
            asset_condition = request.form.get('asset_condition')
            current_user_id = session.get('id')  # Logged-in user

            # 🎯 4️⃣ Handle optional image upload
            image_file = request.files.get('image')
            image_filename = asset['image']  # keep existing image if no upload

            if image_file and allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_filename = f"{asset_id}_{filename}"
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
                image_file.save(upload_path)

            # 🎯 5️⃣ Update asset details
            cursor.execute('''
                UPDATE fixed_assets
                SET 
                    IdentificationNumber = %s,
                    SerialNumber = %s,
                    AssetDescription = %s,
                    department_id = %s,
                    section_id = %s,
                    user_id = %s,
                    OwnershipStatus = %s,
                    AssetCondition = %s,
                    image = %s
                WHERE AssetID = %s
            ''', (
                identification_number,
                serial_number,
                description,
                department_id,
                section_id,
                user_id_selected,
                ownership_status,
                asset_condition,
                image_filename,
                asset_id
            ))

            # 🎯 6️⃣ Log the update in asset_logs
            cursor.execute('''
                INSERT INTO asset_logs (asset_id, user_id, action, log_date, remarks)
                VALUES (%s, %s, %s, NOW(), %s)
            ''', (asset_id, current_user_id, 'edit', 'Asset details updated'))

            conn.commit()
            flash("✅ Asset updated successfully!", "success")
            return redirect(url_for('fixed_assets_blueprint.fixed_assets'))

    except Exception as e:
        conn.rollback()
        flash(f"❌ Error updating asset: {str(e)}", "danger")

    finally:
        cursor.close()
        conn.close()

    # 🎯 7️⃣ Render edit page
    return render_template(
        'fixed_assets/edit_fixed_asset.html',
        asset=asset,
        departments=departments,
        sections=sections,
        users=users
    )





    







@blueprint.route('/delete_fixed_asset/<int:asset_id>', methods=['GET', 'POST'])
def delete_fixed_asset(asset_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch the asset and any relevant info
        cursor.execute('SELECT * FROM fixed_assets WHERE AssetID = %s', (asset_id,))
        asset = cursor.fetchone()

        if not asset:
            flash('Fixed Asset not found.', 'warning')
        else:
            # Delete the asset
            cursor.execute('DELETE FROM fixed_assets WHERE AssetID = %s', (asset_id,))
            connection.commit()

            # Log deletion in inventory_logs
            log_query = '''
                INSERT INTO inventory_logs (
                    asset_id, quantity_change, log_date, reason, user_id
                ) VALUES (%s, %s, NOW(), %s, %s)
            '''
            log_values = (
                asset_id,       # asset_id
                0,              # quantity_change (deletion log only)
                'delete',       # reason
                session.get('id') or 1  # user_id (replace with session user ID if available)
            )
            cursor.execute(log_query, log_values)
            connection.commit()

            flash('Fixed Asset deleted and inventory log updated.', 'success')

    except Exception as e:
        flash(f'Error deleting fixed asset: {e}', 'danger')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('fixed_assets_blueprint.fixed_assets'))







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
