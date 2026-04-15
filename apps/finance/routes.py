import pytz
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from jinja2 import TemplateNotFound

from apps import get_db_connection
from apps.finance import blueprint

# --- Helpers ---

def get_kampala_time():
    """Returns current time in Africa/Kampala."""
    return datetime.now(pytz.timezone("Africa/Kampala"))

def get_segment(request):
    """Extracts the current page name from the request path."""
    try:
        segment = request.path.split('/')[-1]
        return segment if segment != '' else 'finance'
    except:
        return None

# --- Routes ---

@blueprint.route('/fees-summary')
def fees_summary():
    """
    Financial Dashboard: Displays total revenue, collections, 
    and the current fee structure.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # 1. Aggregate Financial Metrics
        cursor.execute('''
            SELECT 
                COALESCE(SUM(amount_charged), 0) as total_billed,
                COALESCE(SUM(amount_paid), 0) as total_collected,
                COALESCE(SUM(balance), 0) as total_outstanding
            FROM student_ledger
        ''')
        stats = cursor.fetchone()

        # 2. Fetch Fee Structure (Joined directly on study_year_id)
        cursor.execute('''
            SELECT 
                fs.*, 
                t.term_name, 
                y.year_name, 
                c.class_name
            FROM fee_structure fs
            LEFT JOIN terms t ON fs.term_id = t.term_id
            LEFT JOIN study_year y ON fs.study_year_id = y.year_id
            LEFT JOIN classes c ON fs.class_id = c.class_id
            ORDER BY y.year_name DESC, t.term_name ASC, c.class_name ASC
        ''')
        fees = cursor.fetchall()

        # 3. Fetch Metadata for Dropdowns
        # Join terms with study_year so dropdowns show "Term 1 (2026)"
        cursor.execute('SELECT * FROM study_year ORDER BY year_name DESC')
        study_years = cursor.fetchall()

        cursor.execute('''
            SELECT t.*, y.year_name 
            FROM terms t 
            JOIN study_year y ON t.year_id = y.year_id 
            ORDER BY y.year_name DESC, t.start_on DESC
        ''')
        terms = cursor.fetchall()

        cursor.execute('SELECT * FROM classes ORDER BY class_name ASC')
        classes = cursor.fetchall()
        
        return render_template(
            'finance/fees_dashboard.html', 
            stats=stats, 
            fees=fees,
            study_years=study_years,
            terms=terms,
            classes=classes,
            segment='fees_management'
        )
        
    except Exception as e:
        flash(f"Error loading financial data: {str(e)}", "danger")
        return redirect(url_for('home_blueprint.index'))
    finally:
        cursor.close()
        connection.close()



@blueprint.route('/add-fee', methods=['POST'])
def add_fee():
    """Defines or updates a billing rule for a specific class, term, and year."""
    # Capture the new year_id along with other form data
    study_year_id = request.form.get('year_id')
    term_id       = request.form.get('term_id')
    class_id      = request.form.get('class_id')
    amount        = request.form.get('amount')
    category      = request.form.get('category', 'Tuition')

    # Basic validation
    if not all([study_year_id, term_id, class_id, amount]):
        flash("Missing required fields. Please fill all options.", "warning")
        return redirect(url_for('finance_blueprint.fees_summary'))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Using INSERT ... ON DUPLICATE KEY UPDATE is cleaner if you have a 
        # unique index on (study_year_id, term_id, class_id, category)
        cursor.execute('''
            INSERT INTO fee_structure 
                (study_year_id, term_id, class_id, amount, category)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE amount = VALUES(amount)
        ''', (study_year_id, term_id, class_id, amount, category))
        
        connection.commit()
        flash(f"Fee structure for {category} successfully saved.", "success")
        
    except Exception as e:
        connection.rollback()
        flash(f"Database Error: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('finance_blueprint.fees_summary'))







@blueprint.route('/edit-fee/<int:fee_id>', methods=['POST'])
def edit_fee(fee_id):
    """Updates an existing fee configuration based on fee_id."""
    study_year_id = request.form.get('year_id')
    term_id       = request.form.get('term_id')
    class_id      = request.form.get('class_id')
    amount        = request.form.get('amount')
    category      = request.form.get('category')

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute('''
            UPDATE fee_structure 
            SET study_year_id = %s, 
                term_id = %s, 
                class_id = %s, 
                amount = %s, 
                category = %s
            WHERE fee_id = %s
        ''', (study_year_id, term_id, class_id, amount, category, fee_id))
        
        connection.commit()
        flash("Fee structure updated successfully.", "success")
            
    except Exception as e:
        connection.rollback()
        # Handle unique constraint errors (e.g., if class/term/category combo exists)
        flash(f"Error: Could not update fee. {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('finance_blueprint.fees_summary'))



@blueprint.route('/delete-fee/<int:fee_id>', methods=['POST'])
def delete_fee(fee_id):
    """Removes a fee configuration."""
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # Check if this fee is already being used in the ledger (optional safety check)
        # If you have a foreign key with 'ON DELETE RESTRICT', 
        # MySQL will prevent this automatically if students are already billed.
        
        cursor.execute('DELETE FROM fee_structure WHERE fee_id = %s', (fee_id,))
        connection.commit()
        
        if cursor.rowcount > 0:
            flash("Fee rule deleted successfully.", "success")
        else:
            flash("Fee rule not found or already deleted.", "warning")
            
    except Exception as e:
        connection.rollback()
        flash(f"Error: Cannot delete this fee. It may be linked to student records. {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('finance_blueprint.fees_summary'))



    
    



# --- Generic Routing ---

@blueprint.route('/<template>')
def route_template(template):
    """Dynamic routing for finance-related HTML files."""
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)
        # Serving from app/templates/finance/
        return render_template(f"finance/{template}", segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404
    except Exception:
        return render_template('home/page-500.html'), 500