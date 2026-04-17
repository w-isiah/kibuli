import pytz
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from jinja2 import TemplateNotFound

from apps import get_db_connection
from apps.church import blueprint # Ensure this matches your blueprint registration

# --- Helpers ---

def get_kampala_time():
    """Returns current time in Africa/Kampala."""
    return datetime.now(pytz.timezone("Africa/Kampala"))

def get_segment(request):
    """Extracts the current page name from the request path."""
    try:
        segment = request.path.split('/')[-1]
        return segment if segment != '' else 'manage_churches'
    except:
        return None

# --- Routes ---

@blueprint.route('/manage_churches')
def manage_churches():
    """
    Displays local churches, their parent parishes, and basic stats.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # 1. Aggregate Church Metrics based on your schema
        cursor.execute('''
            SELECT 
                COUNT(id) as total_churches,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count,
                COUNT(DISTINCT district) as total_districts
            FROM church
        ''')
        stats = cursor.fetchone()

        # 2. Fetch Church List with Parish Name JOIN
        # Note: Archdeaconry is accessed via the Parish link if needed in the UI
        cursor.execute('''
            SELECT 
                c.*, 
                p.name as parish_name
            FROM church c
            JOIN parishes p ON c.parish_id = p.id
            ORDER BY c.created_at DESC
        ''')
        churches = cursor.fetchall()

        # 3. Fetch Parishes for the "Add Church" dropdown
        cursor.execute('SELECT id, name FROM parishes WHERE is_active = 1 ORDER BY name ASC')
        parishes = cursor.fetchall()

        return render_template(
            'churches/church_list.html',
            stats=stats, 
            churches=churches,
            parishes=parishes,
            segment='manage_churches'
        )
        
    except Exception as e:
        flash(f"Error loading Church data: {str(e)}", "danger")
        return redirect(url_for('home_blueprint.index'))
    finally:
        cursor.close()
        connection.close()


@blueprint.route('/add_church', methods=['POST'])
def add_church():
    """Registers a new local Church linked to a Parish."""
    
    parish_id   = request.form.get('parish_id')
    church_name = request.form.get('church_name', '').strip()
    district    = request.form.get('district', '').strip()

    if not all([parish_id, church_name]):
        flash("Missing required fields: Parish and Church Name are mandatory.", "warning")
        return redirect(url_for('church_blueprint.manage_churches'))

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        # Schema fields: parish_id, church_name, district, is_active
        cursor.execute('''
            INSERT INTO church 
                (parish_id, church_name, district, is_active)
            VALUES (%s, %s, %s, 1)
        ''', (parish_id, church_name, district))
        
        connection.commit()
        flash(f"Successfully registered {church_name} church.", "success")
        
    except Exception as e:
        connection.rollback()
        flash(f"Database Error: {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('church_blueprint.manage_churches'))


@blueprint.route('/edit_church/<int:church_id>', methods=['POST'])
def edit_church(church_id):
    """Updates an existing Church record based on id."""
    
    parish_id   = request.form.get('parish_id')
    church_name = request.form.get('church_name', '').strip()
    district    = request.form.get('district', '').strip()
    is_active   = 1 if request.form.get('is_active') in ['True', '1', 'on'] else 0

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE church 
            SET parish_id = %s, 
                church_name = %s, 
                district = %s, 
                is_active = %s
            WHERE id = %s
        ''', (parish_id, church_name, district, is_active, church_id))
        
        connection.commit()
        flash(f"Church '{church_name}' updated successfully.", "success")
            
    except Exception as e:
        connection.rollback()
        flash(f"Error: Could not update church details. {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('church_blueprint.manage_churches'))


@blueprint.route('/delete_church/<int:church_id>', methods=['POST'])
def delete_church(church_id):
    """Removes a church record."""
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('DELETE FROM church WHERE id = %s', (church_id,))
        connection.commit()
        
        if cursor.rowcount > 0:
            flash("Church record removed from the system.", "success")
        else:
            flash("Church record not found.", "warning")
            
    except Exception as e:
        connection.rollback()
        flash(f"Error: Cannot delete this church. Check if members are still linked to it.", "danger")
    finally:
        connection.close()

    return redirect(url_for('church_blueprint.manage_churches'))

# --- Generic Routing ---

@blueprint.route('/<template>')
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)
        return render_template(f"churches/{template}", segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404
    except Exception:
        return render_template('home/page-500.html'), 500