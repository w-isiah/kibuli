from apps.asset_inventory import blueprint
from flask import render_template, request, redirect, url_for, flash, session
from mysql.connector import Error
from apps import get_db_connection
from jinja2 import TemplateNotFound





@blueprint.route('/assets_inventory_index')
def assets_inventory_index():
    """Fetches all inventory records and renders the Asset Inventory page."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # ✅ SQL query joins inventory with fixed_assets and locations
    cursor.execute("""
        SELECT 
            ai.InventoryID,
            f.IdentificationNumber,
            f.AssetDescription,
            l.LocationName,
            ai.RecordedQuantity,
            ai.VerifiedQuantity,
            ai.LastVerified,
            ai.AssetCondition,
            ai.Remarks
        FROM asset_inventory ai
        JOIN fixed_assets f ON ai.AssetID = f.AssetID
        JOIN locations l ON ai.LocationID = l.LocationID
        ORDER BY f.AssetDescription ASC
    """)
    inventory = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('asset_inventory/asset_inventory.html', inventory=inventory)






@blueprint.route('/add_inventory', methods=['GET', 'POST'])
def add_inventory():
    """Handles adding a new inventory record."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Fetch assets for dropdown
    cursor.execute("""
        SELECT AssetID, AssetDescription, IdentificationNumber 
        FROM fixed_assets 
        ORDER BY AssetDescription ASC
    """)
    assets = cursor.fetchall()

    # Fetch locations with room names for dropdown
    cursor.execute("""
        SELECT 
            l.LocationID, 
            l.LocationName, 
            l.description,
            l.room_id,
            r.room_name
        FROM locations l
        LEFT JOIN rooms r ON l.room_id = r.room_id
        ORDER BY l.LocationName ASC
    """)
    locations = cursor.fetchall()

    if request.method == 'POST':
        asset_id = request.form.get('asset_id')
        location_id = request.form.get('location_id')
        recorded_qty = request.form.get('recorded_qty')
        verified_qty = request.form.get('verified_qty')
        condition = request.form.get('condition')
        remarks = request.form.get('remarks')

        # Basic validation
        if not asset_id or not location_id or not recorded_qty:
            flash("Please fill out all required fields!", "warning")
        else:
            try:
                # Check if asset already exists at that location
                cursor.execute("""
                    SELECT * FROM asset_inventory
                    WHERE AssetID = %s AND LocationID = %s
                """, (asset_id, location_id))
                existing = cursor.fetchone()

                if existing:
                    flash("This asset already exists in the selected location!", "warning")
                else:
                    # Insert new inventory record
                    cursor.execute("""
                        INSERT INTO asset_inventory (
                            AssetID, LocationID, RecordedQuantity, VerifiedQuantity, 
                            AssetCondition, Remarks, LastVerified
                        ) VALUES (%s, %s, %s, %s, %s, %s, CURDATE())
                    """, (
                        asset_id,
                        location_id,
                        recorded_qty,
                        verified_qty or None,
                        condition or 'Good',
                        remarks or None
                    ))
                    connection.commit()
                    flash("Asset successfully added to inventory!", "success")

            except Exception as err:
                flash(f"Error: {err}", "danger")

    cursor.close()
    connection.close()

    return render_template(
        'asset_inventory/add_inventory.html',
        assets=assets,
        locations=locations
    )









@blueprint.route('/edit_inventory/<int:inventory_id>', methods=['GET', 'POST'])
def edit_inventory(inventory_id):
    """Handles editing an existing inventory record."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        asset_id = request.form.get('asset_id')
        location_id = request.form.get('location_id')
        recorded_qty = request.form.get('recorded_qty')
        verified_qty = request.form.get('verified_qty')
        condition = request.form.get('condition')
        remarks = request.form.get('remarks')

        try:
            cursor.execute("""
                UPDATE asset_inventory
                SET AssetID = %s,
                    LocationID = %s,
                    RecordedQuantity = %s,
                    VerifiedQuantity = %s,
                    AssetCondition = %s,
                    Remarks = %s,
                    UpdatedAt = NOW()
                WHERE InventoryID = %s
            """, (asset_id, location_id, recorded_qty, verified_qty, condition, remarks, inventory_id))
            connection.commit()

            flash("Inventory record updated successfully!", "success")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('asset_inventory_blueprint.assets_inventory_index'))

    # GET request → Load data to prefill the form
    cursor.execute("""
        SELECT 
            ai.*, 
            f.AssetDescription, 
            f.IdentificationNumber, 
            l.LocationName
        FROM asset_inventory ai
        JOIN fixed_assets f ON ai.AssetID = f.AssetID
        JOIN locations l ON ai.LocationID = l.LocationID
        WHERE ai.InventoryID = %s
    """, (inventory_id,))
    inventory = cursor.fetchone()

    # Load assets and locations for dropdowns
    cursor.execute("SELECT AssetID, IdentificationNumber, AssetDescription FROM fixed_assets ORDER BY AssetDescription ASC")
    assets = cursor.fetchall()

    cursor.execute("SELECT LocationID, LocationName FROM locations ORDER BY LocationName ASC")
    locations = cursor.fetchall()

    cursor.close()
    connection.close()

    if inventory:
        return render_template(
            'asset_inventory/edit_inventory.html',
            inventory=inventory,
            assets=assets,
            locations=locations
        )
    else:
        flash("Inventory record not found.", "danger")
        return redirect(url_for('asset_inventory_blueprint.assets_inventory_index'))


@blueprint.route('/delete_inventory/<int:inventory_id>')
def delete_inventory(inventory_id):
    """Deletes an inventory record."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM asset_inventory WHERE InventoryID = %s", (inventory_id,))
        connection.commit()
        flash("Inventory record deleted successfully!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('asset_inventory_blueprint.assets_inventory_index'))




@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("categories/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'categories'

        return segment

    except:
        return None
