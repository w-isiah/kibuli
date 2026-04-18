import pytz
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from jinja2 import TemplateNotFound

from apps import get_db_connection
from apps.course_units import blueprint # Ensure this matches your new blueprint registration

# --- Helpers ---

def get_kampala_time():
    """Returns current time in Africa/Kampala."""
    return datetime.now(pytz.timezone("Africa/Kampala"))

def get_segment(request):
    """Extracts the current page name from the request path."""
    try:
        segment = request.path.split('/')[-1]
        return segment if segment != '' else 'manage_course_units'
    except:
        return None

# --- Routes ---

@blueprint.route('/manage_course_units')
def manage_course_units():
    """Displays course units, their parent courses, and metrics."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # 1. Aggregate Unit Metrics
        cursor.execute('''
            SELECT 
                COUNT(id) as total_units,
                AVG(credit_units) as avg_credits,
                COUNT(DISTINCT course_id) as total_courses
            FROM course_units
        ''')
        stats = cursor.fetchone()

        # 2. Fetch Units with parent Course details
        cursor.execute('''
            SELECT 
                cu.*, 
                c.course_name 
            FROM course_units cu
            JOIN courses c ON cu.course_id = c.id
            ORDER BY cu.created_at DESC
        ''')
        units = cursor.fetchall()

        # 3. Fetch all Courses for the "Add Unit" parent dropdown
        cursor.execute('SELECT id, course_name FROM courses ORDER BY course_name ASC')
        courses = cursor.fetchall()

        return render_template(
            'course_units/list.html',
            stats=stats, 
            units=units,
            courses=courses,
            segment='manage_course_units'
        )
        
    except Exception as e:
        flash(f"Error loading Unit data: {str(e)}", "danger")
        return redirect(url_for('home_blueprint.index'))
    finally:
        cursor.close()
        connection.close()


@blueprint.route('/add_course_unit', methods=['POST'])
def add_course_unit():
    """Registers a new Unit linked to a Course."""
    
    course_id    = request.form.get('course_id')
    unit_name    = request.form.get('unit_name', '').strip()
    unit_code    = request.form.get('unit_code', '').strip()
    credits      = request.form.get('credit_units', 3)
    semester     = request.form.get('semester', '1')
    term         = request.form.get('term', '1')
    description  = request.form.get('description', '').strip()

    if not all([course_id, unit_name, unit_code]):
        flash("Missing required fields: Parent Course, Name, and Code are mandatory.", "warning")
        return redirect(url_for('course_units_blueprint.manage_course_units'))

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO course_units 
                (course_id, unit_name, unit_code, credit_units, semester, term, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (course_id, unit_name, unit_code, credits, semester, term, description))
        
        connection.commit()
        flash(f"Successfully registered {unit_name} ({unit_code}).", "success")
        
    except Exception as e:
        connection.rollback()
        flash(f"Database Error: {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('course_units_blueprint.manage_course_units'))


@blueprint.route('/edit_course_unit/<int:unit_id>', methods=['POST'])
def edit_course_unit(unit_id):
    """Updates an existing Unit record."""
    
    course_id    = request.form.get('course_id')
    unit_name    = request.form.get('unit_name', '').strip()
    unit_code    = request.form.get('unit_code', '').strip()
    credits      = request.form.get('credit_units')
    semester     = request.form.get('semester')
    term         = request.form.get('term')
    description  = request.form.get('description', '').strip()

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE course_units 
            SET course_id = %s, 
                unit_name = %s, 
                unit_code = %s, 
                credit_units = %s,
                semester = %s,
                term = %s,
                description = %s
            WHERE id = %s
        ''', (course_id, unit_name, unit_code, credits, semester, term, description, unit_id))
        
        connection.commit()
        flash(f"Unit '{unit_name}' updated successfully.", "success")
            
    except Exception as e:
        connection.rollback()
        flash(f"Error: Could not update unit details. {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('course_units_blueprint.manage_course_units'))


@blueprint.route('/delete_course_unit/<int:unit_id>', methods=['POST'])
def delete_course_unit(unit_id):
    """Removes a unit record."""
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('DELETE FROM course_units WHERE id = %s', (unit_id,))
        connection.commit()
        
        if cursor.rowcount > 0:
            flash("Unit record removed.", "success")
        else:
            flash("Unit record not found.", "warning")
            
    except Exception as e:
        connection.rollback()
        flash(f"Error: Cannot delete this unit. {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('course_units_blueprint.manage_course_units'))


# --- Generic Routing ---

@blueprint.route('/<template>')
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)
        return render_template(f"course_units/{template}", segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404
    except Exception:
        return render_template('home/page-500.html'), 500