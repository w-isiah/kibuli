import pytz
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from jinja2 import TemplateNotFound

from apps import get_db_connection
from apps.courses import blueprint 

# --- Helpers ---

def get_kampala_time():
    """Returns current time in Africa/Kampala."""
    return datetime.now(pytz.timezone("Africa/Kampala"))

def get_segment(request):
    """Extracts the current page name from the request path."""
    try:
        segment = request.path.split('/')[-1]
        return segment if segment != '' else 'manage_courses'
    except:
        return None

# --- Routes ---

@blueprint.route('/manage_courses')
def manage_courses():
    """Displays academic courses, their parent colleges, and metrics."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # 1. Aggregate Course Metrics
        cursor.execute('''
            SELECT 
                COUNT(id) as total_courses,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count,
                COUNT(DISTINCT level) as total_levels
            FROM courses
        ''')
        stats = cursor.fetchone()

        # 2. Fetch Course List with Affiliation (College) Name JOIN
        cursor.execute('''
            SELECT 
                c.*, 
                a.name as affiliation_name
            FROM courses c
            JOIN affiliations a ON c.affiliation_id = a.id
            ORDER BY c.created_at DESC
        ''')
        courses = cursor.fetchall()

        # 3. Fetch ONLY 'Active' Affiliations for the "Add Course" dropdown
        # This aligns with your MariaDB schema ENUM ('Active', 'Inactive', 'Suspended', 'Dissolved')
        cursor.execute('''
            SELECT id, name 
            FROM affiliations 
            WHERE status = 'Active' 
            ORDER BY name ASC
        ''')
        affiliations = cursor.fetchall()

        return render_template(
            'courses/course_list.html',
            stats=stats, 
            courses=courses,
            affiliations=affiliations,
            segment='manage_courses'
        )
        
    except Exception as e:
        flash(f"Error loading Course data: {str(e)}", "danger")
        return redirect(url_for('home_blueprint.index'))
    finally:
        cursor.close()
        connection.close()


@blueprint.route('/add_course', methods=['POST'])
def add_course():
    """Registers a new Course linked to an Active Affiliation."""
    
    affiliation_id = request.form.get('affiliation_id')
    course_name    = request.form.get('course_name', '').strip()
    course_code    = request.form.get('course_code', '').strip()
    version        = request.form.get('version', '1.0').strip()
    duration       = request.form.get('duration_years', 3)
    level          = request.form.get('level', 'Bachelor')

    if not all([affiliation_id, course_name, course_code]):
        flash("Missing required fields: Affiliation, Name, and Code are mandatory.", "warning")
        return redirect(url_for('courses_blueprint.manage_courses'))

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO courses 
                (affiliation_id, course_name, course_code, version, duration_years, level, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
        ''', (affiliation_id, course_name, course_code, version, duration, level))
        
        connection.commit()
        flash(f"Successfully registered {course_name} ({course_code}).", "success")
        
    except Exception as e:
        connection.rollback()
        flash(f"Database Error: {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('courses_blueprint.manage_courses'))


@blueprint.route('/edit_course/<int:course_id>', methods=['POST'])
def edit_course(course_id):
    """Updates an existing Course record."""
    
    affiliation_id = request.form.get('affiliation_id')
    course_name    = request.form.get('course_name', '').strip()
    course_code    = request.form.get('course_code', '').strip()
    version        = request.form.get('version', '').strip()
    duration       = request.form.get('duration_years')
    level          = request.form.get('level')
    # Convert checkbox/select values to integer for DB storage
    is_active      = 1 if request.form.get('is_active') in ['True', '1', 'on'] else 0

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE courses 
            SET affiliation_id = %s, 
                course_name = %s, 
                course_code = %s, 
                version = %s,
                duration_years = %s,
                level = %s,
                is_active = %s
            WHERE id = %s
        ''', (affiliation_id, course_name, course_code, version, duration, level, is_active, course_id))
        
        connection.commit()
        flash(f"Course '{course_name}' updated successfully.", "success")
            
    except Exception as e:
        connection.rollback()
        flash(f"Error: Could not update course details. {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('courses_blueprint.manage_courses'))


@blueprint.route('/delete_course/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    """Removes a course record."""
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute('DELETE FROM courses WHERE id = %s', (course_id,))
        connection.commit()
        
        if cursor.rowcount > 0:
            flash("Course record removed from the system.", "success")
        else:
            flash("Course record not found.", "warning")
            
    except Exception as e:
        connection.rollback()
        flash(f"Error: Cannot delete this course. {str(e)}", "danger")
    finally:
        connection.close()

    return redirect(url_for('courses_blueprint.manage_courses'))


# --- Generic Routing ---

@blueprint.route('/<template>')
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)
        return render_template(f"courses/{template}", segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404
    except Exception:
        return render_template('home/page-500.html'), 500