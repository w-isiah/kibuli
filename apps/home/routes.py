from flask import render_template, request, session, flash, redirect, url_for
from apps.utils.decorators import login_required
from jinja2 import TemplateNotFound
from apps import get_db_connection
from apps.home import blueprint
import logging

@blueprint.route('/index')
@login_required
def index():
    user_id = session.get('id')
    
    if not user_id:
        return redirect(url_for('authentication_blueprint.login'))

    # Role-to-Template Mapping
    role_templates = {
        'admin':             ('home/index.html', 'index'),
        'director':          ('home/index.html', 'index'),
        'class_teacher':     ('home/class_teacher_index.html', 'index'),
        'inventory_manager': ('home/inventory_manager_index.html', 'index'),
        'assistant_manager': ('home/inventory_manager_index.html', 'index'),
        'section_head':      ('home/inventory_section_head_index.html', 'index'),
        'department_head':   ('home/department_head_index.html', 'index'),
        'super_admin':       ('home/sa_index.html', 'sa_index'),
        'teacher':           ('home/teacher_index.html', 'index'),
        'Head_ICT':          ('home/inventory_ict_head_manager_index.html', 'index'),
        'dos':               ('home/dos_index.html', 'index'),
        'co_ordinator':      ('home/co_ordinator_index.html', 'index'),
        'applicant':         ('home/applicant_index.html', 'index'),
        'other':             ('home/index.html', 'index'),
    }

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:
                # 1. Verify User Role
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                db_user = cursor.fetchone()

                if not db_user:
                    session.clear()
                    return redirect(url_for('authentication_blueprint.login'))

                current_role = db_user['role']


                # 3. Route to Template
                template_config = role_templates.get(current_role)

                if template_config:
                    template_path, segment = template_config
                    return render_template(
                        template_path, 
                        segment=segment,
                    )
                
                flash(f'Role "{current_role}" is not mapped to a dashboard.', 'warning')
                return redirect(url_for('authentication_blueprint.login'))

    except Exception as e:
        logging.error(f"Dashboard Load Error: {str(e)}")
        flash("System error loading dashboard data.", 'danger')
        return redirect(url_for('authentication_blueprint.login'))

@blueprint.route('/<template>')
@login_required
def route_template(template):
    segment = get_segment(request)
    try:
        if not template.endswith('.html'):
            template += '.html'
        return render_template(f"home/{template}", segment=segment)
    except TemplateNotFound:
        return render_template('home/page-404.html', segment=segment), 404
    except Exception as e:
        logging.error(f"Route Template Error: {str(e)}")
        return render_template('home/page-500.html', segment=segment), 500

def get_segment(request):
    segment = request.path.strip('/').split('/')[-1]
    return segment if segment else 'index'