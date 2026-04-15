import os
import random
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session
from jinja2 import TemplateNotFound
from werkzeug.utils import secure_filename

# Database imports
import mysql.connector
from mysql.connector import Error
from apps import get_db_connection
from apps.admissions import blueprint

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)








@blueprint.route('/admission_list')
def admission_list():
    # 1. Get the database assigned to this user from the session
    user_db = session.get('assigned_db')

    # 2. Pass the user's specific database to the connection function
    connection = get_db_connection(db_name=user_db)
    cursor = connection.cursor(dictionary=True)

    try:
        # --- The rest of your code remains exactly the same ---
        
        # 1. Load filter options
        cursor.execute('SELECT class_id, class_name FROM classes ORDER BY class_name')
        class_list = cursor.fetchall()
        cursor.execute('SELECT year_id, year_name FROM study_year ORDER BY year_name DESC')
        year_list = cursor.fetchall()
        cursor.execute('SELECT term_id, term_name FROM terms ORDER BY term_name')
        term_list = cursor.fetchall()

        # 2. Get search/filter parameters
        status = request.args.get('status', '').strip()
        class_id = request.args.get('class_id', '').strip()
        year_id = request.args.get('year_id', '').strip()
        term_id = request.args.get('term_id', '').strip()
        search_name = request.args.get('name', '').strip()
        search_reg = request.args.get('reg_no', '').strip()
        
        # New Date Range Parameters
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        params = {}
        filters = []

        if status:
            filters.append("a.admission_status = %(status)s")
            params['status'] = status
        if class_id:
            filters.append("a.class_id = %(class_id)s")
            params['class_id'] = class_id
        if year_id:
            filters.append("a.year_id = %(year_id)s")
            params['year_id'] = year_id
        if term_id:
            filters.append("a.term_id = %(term_id)s")
            params['term_id'] = term_id
        if search_name:
            filters.append("(p.first_name LIKE %(name)s OR p.last_name LIKE %(name)s OR p.other_name LIKE %(name)s)")
            params['name'] = f"%{search_name}%"
        if search_reg:
            filters.append("p.reg_no LIKE %(reg_no)s")
            params['reg_no'] = f"%{search_reg}%"

        # --- Date Range Logic ---
        if start_date:
            filters.append("DATE(a.date_created) >= %(start_date)s")
            params['start_date'] = start_date
        if end_date:
            filters.append("DATE(a.date_created) <= %(end_date)s")
            params['end_date'] = end_date

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        query = f"""
            SELECT 
                a.admission_id, p.reg_no,
                CONCAT_WS(' ', p.first_name, p.other_name, p.last_name) AS full_name,
                COALESCE(c.class_name, 'N/A') AS class_name,
                COALESCE(sy.year_name, 'N/A') AS study_year,
                COALESCE(t.term_name, 'N/A') AS term_name,
                a.admission_status, a.rejection_reason, a.date_created
            FROM admissions a
            INNER JOIN pupils_admission p ON a.pupil_id = p.pupil_id
            LEFT JOIN study_year sy ON a.year_id = sy.year_id
            LEFT JOIN terms t ON a.term_id = t.term_id
            LEFT JOIN classes c ON CAST(a.class_id AS UNSIGNED) = c.class_id
            {where_clause}
            ORDER BY a.date_created DESC
        """
        
        cursor.execute(query, params)
        admissions = cursor.fetchall()

        return render_template(
            'admissions/admission_list.html',
            admissions=admissions,
            class_list=class_list,
            year_list=year_list,
            term_list=term_list,
            filters={
                'status': status, 'class_id': class_id, 'year_id': year_id,
                'term_id': term_id, 'name': search_name, 'reg_no': search_reg, 
                'start_date': start_date, 'end_date': end_date
            }
        )
        
    finally:
        cursor.close()
        connection.close()        



        


@blueprint.route('/add_admission', methods=['GET', 'POST'])
def add_admission():
    """Display and process admission application form"""

    user_id = session.get('id')
    if not user_id:
        flash("Session expired. Please log in again.", "danger")
        return redirect(url_for('authentication_blueprint.login'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # =====================================================
        # GET REQUEST
        # =====================================================
        if request.method == 'GET':
            cursor.execute("SELECT * FROM classes ORDER BY class_name ASC")
            classes = cursor.fetchall()

            cursor.execute("SELECT * FROM terms")
            terms = cursor.fetchall()

            cursor.execute("SELECT year_id, year_name FROM study_year ORDER BY year_name")
            study_years = cursor.fetchall()

            return render_template(
                'admissions/add_admission.html',
                classes=classes,
                terms=terms,
                study_years=study_years,
                segment='add_admission'
            )

        # =====================================================
        # POST REQUEST
        # =====================================================
        connection.start_transaction()

        # -------------------------------
        # 1. Validate Required Fields
        # -------------------------------
        required_fields = [
            'first_name', 'last_name',
            'gender', 'class_id',
            'term_id', 'year_id'
        ]

        for field in required_fields:
            if not request.form.get(field):
                raise ValueError("All required fields must be filled.")

        class_id = request.form['class_id']
        term_id = request.form['term_id']
        year_id = request.form['year_id']

        # -------------------------------
        # 2. Generate Unique Reg Number
        # -------------------------------
        def generate_unique_reg_no():
            current_year = datetime.now().year
            while True:
                reg = f"SJS/{current_year}/{random.randint(1000, 9999)}"
                cursor.execute(
                    "SELECT 1 FROM pupils_admission WHERE reg_no = %s",
                    (reg,)
                )
                if not cursor.fetchone():
                    return reg

        reg_no = generate_unique_reg_no()

        # -------------------------------
        # 3. Insert Guardian
        # -------------------------------
        guardian_values = (
            request.form.get('guardian_name', '').strip(),
            request.form.get('relationship', '').strip(),
            request.form.get('phone_primary', '').strip(),
            request.form.get('phone_alt') or None,
            request.form.get('email') or None,
            request.form.get('occupation') or None,
            request.form.get('physical_address', '').strip()
        )

        cursor.execute("""
            INSERT INTO guardians
            (full_name, relationship, phone_primary, phone_alt,
             email, occupation, physical_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, guardian_values)

        guardian_id = cursor.lastrowid

        # -------------------------------
        # 4. Fetch Admission Fee
        # -------------------------------
        cursor.execute("""
            SELECT amount
            FROM fee_structure
            WHERE study_year_id = %s
              AND term_id = %s
              AND class_id = %s
              AND category = 'Admission'
            LIMIT 1
        """, (year_id, term_id, class_id))

        fee_row = cursor.fetchone()

        if not fee_row:
            raise ValueError("Admission fee not configured for selected class/term/year.")

        admission_fee_amount = fee_row['amount']

        # -------------------------------
        # 5. Insert Application Fee Record
        # -------------------------------
        cursor.execute("""
            INSERT INTO application_fee
            (application_fee, payment_status)
            VALUES (%s, 'Unpaid')
        """, (admission_fee_amount,))

        form_id = cursor.lastrowid

        # -------------------------------
        # 6. Insert Pupil Record
        # -------------------------------
        pupil_values = (
            guardian_id,
            reg_no,
            request.form['first_name'].strip(),
            request.form.get('other_name') or None,
            request.form['last_name'].strip(),
            request.form.get('date_of_birth'),
            request.form['gender'],
            request.form.get('nationality', 'Ugandan'),
            request.form.get('address'),
            request.form.get('languages_spoken') or None,
            request.form.get('emergency_contact') or None,
            request.form.get('medical_info') or None,
            request.form.get('special_needs') or None,
            request.form.get('prev_school_name') or None,
            request.form.get('reason_for_leaving') or None,
            class_id,
            term_id,
            year_id
        )

        cursor.execute("""
            INSERT INTO pupils_admission
            (guardian_id, reg_no, first_name, other_name, last_name,
             date_of_birth, gender, nationality, address,
             languages_spoken, emergency_contact, medical_info,
             special_needs, prev_school_name, reason_for_leaving,
             class_id, term_id, year_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s)
        """, pupil_values)

        pupil_id = cursor.lastrowid

        # -------------------------------
        # 7. Insert Admission Workflow
        # -------------------------------
        cursor.execute("""
            INSERT INTO admissions
            (pupil_id, class_id, term_id, year_id,
             admission_status, created_by,
             form_id, date_created)
            VALUES (%s, %s, %s, %s,
                    'Pending', %s,
                    %s, NOW())
        """, (
            pupil_id,
            class_id,
            term_id,
            year_id,
            user_id,
            form_id
        ))

        # -------------------------------
        # 8. Commit Transaction
        # -------------------------------
        connection.commit()

        flash(
            f"Admission {reg_no} submitted successfully. "
            f"Application Fee: {admission_fee_amount} (Unpaid)",
            "success"
        )

        return redirect(url_for('admissions_blueprint.add_admission'))

    except Exception as e:
        connection.rollback()
        current_app.logger.error(f"Admission Error: {str(e)}")
        flash(str(e), "danger")
        return redirect(url_for('admissions_blueprint.add_admission'))

    finally:
        cursor.close()
        connection.close()




























from flask import current_app, session, request, flash, redirect, url_for
from mysql.connector import IntegrityError

@blueprint.route('/update_status/<int:admission_id>/<string:new_status>', methods=['POST'])
def update_admission_status(admission_id, new_status):
    """
    Workflow:
      - If Approved:
          1) Lock admissions row, ensure it exists and is Pending.
          2) Update admissions.admission_status = 'Approved'.
          3) Read the admissions row to get pupil_id (applicant id).
          4) Lock and read pupils_admission row for that pupil_id.
          5) Insert a new row into pupils using the data from pupils_admission.
      - If Rejected:
          Validate rejection_reason and update admissions accordingly.
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Lock the admissions row first
        cursor.execute("""
            SELECT *
            FROM admissions
            WHERE admission_id = %s
            FOR UPDATE
        """, (admission_id,))
        admission = cursor.fetchone()

        if not admission:
            flash("Admission record not found.", "danger")
            return redirect(url_for('admissions_blueprint.admission_list'))

        # Prevent double-processing; only allow if Pending
        current_status = admission.get('admission_status')
        if current_status and current_status != 'Pending':
            flash("This application has already been processed.", "warning")
            return redirect(url_for('admissions_blueprint.admission_list'))

        # APPROVE path
        if new_status == "Approved":
            # 1) Update admissions status to Approved
            cursor.execute("""
                UPDATE admissions
                SET admission_status = 'Approved'
                WHERE admission_id = %s
            """, (admission_id,))

            # 2) Re-read the admissions row (still locked) to get linked pupil_id
            cursor.execute("""
                SELECT *
                FROM admissions
                WHERE admission_id = %s
                FOR UPDATE
            """, (admission_id,))
            admission = cursor.fetchone()
            src_pupil_id = admission.get('pupil_id')

            if not src_pupil_id:
                # Nothing to copy from — rollback and inform user
                connection.rollback()
                flash("Admission has no linked applicant record to register.", "danger")
                return redirect(url_for('admissions_blueprint.admission_list'))

            # 3) Lock and fetch applicant details from pupils_admission
            cursor.execute("""
                SELECT *
                FROM pupils_admission
                WHERE pupil_id = %s
                FOR UPDATE
            """, (src_pupil_id,))
            applicant = cursor.fetchone()

            if not applicant:
                connection.rollback()
                flash("Applicant details not found for this admission.", "danger")
                return redirect(url_for('admissions_blueprint.admission_list'))

            # 4) Check reg_no uniqueness in pupils (fail-fast)
            reg_no = applicant.get('reg_no')
            if reg_no:
                cursor.execute("SELECT pupil_id FROM pupils WHERE reg_no = %s", (reg_no,))
                if cursor.fetchone():
                    connection.rollback()
                    flash(f"Cannot approve: reg_no '{reg_no}' already exists in pupils.", "danger")
                    return redirect(url_for('admissions_blueprint.admission_list'))

            # 5) Build INSERT values in the same order as pupils table columns
            values = (
                applicant.get('guardian_id'),
                applicant.get('reg_no'),
                applicant.get('index_number'),
                applicant.get('nin_number'),
                applicant.get('home_district'),
                applicant.get('emis_number'),
                applicant.get('dorm_id'),
                applicant.get('first_name'),
                applicant.get('other_name'),
                applicant.get('last_name'),
                applicant.get('image'),
                applicant.get('date_of_birth'),
                applicant.get('gender'),
                applicant.get('nationality'),
                applicant.get('languages_spoken'),
                applicant.get('stream_id'),
                applicant.get('class_id'),
                applicant.get('admission_date'),
                applicant.get('year_id'),
                applicant.get('term_id'),
                applicant.get('address'),
                applicant.get('emergency_contact'),
                applicant.get('medical_info'),
                applicant.get('special_needs'),
                applicant.get('prev_school_name'),
                applicant.get('reason_for_leaving'),
                applicant.get('attendance_record'),
                applicant.get('academic_performance'),
                applicant.get('notes'),
                applicant.get('residential_status'),
                session.get('user_id')  # created_by
            )

            cursor.execute("""
                INSERT INTO pupils (
                    guardian_id, reg_no, index_number, nin_number,
                    home_district, emis_number, dorm_id,
                    first_name, other_name, last_name,
                    image, date_of_birth, gender, nationality,
                    languages_spoken, stream_id, class_id,
                    admission_date, year_id, term_id,
                    address, emergency_contact, medical_info,
                    special_needs, prev_school_name, reason_for_leaving,
                    attendance_record, academic_performance,
                    notes, residential_status, created_by
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s
                )
            """, values)

            # Optionally capture the created pupil_id
            new_pupil_id = cursor.lastrowid

            # Commit the transaction (both admissions update and pupils insert)
            connection.commit()

            flash("Application approved and pupil registered successfully.", "success")

        # REJECT path
        elif new_status == "Rejected":
            reason = request.form.get("rejection_reason", "").strip()
            if not reason:
                flash("Rejection reason is required.", "warning")
                return redirect(url_for('admissions_blueprint.admission_list'))

            cursor.execute("""
                UPDATE admissions
                SET admission_status = 'Rejected',
                    rejection_reason = %s,
                    rejected_by = %s,
                    rejected_at = NOW()
                WHERE admission_id = %s
            """, (reason, session.get("user_id"), admission_id))

            connection.commit()
            flash("Application rejected successfully.", "info")

        else:
            flash("Unknown status.", "warning")
            connection.rollback()

    except IntegrityError as ie:
        connection.rollback()
        try:
            current_app.logger.exception("Integrity error updating admission status")
        except Exception:
            print("Integrity error:", ie)
        flash(f"Database integrity error: {ie}", "danger")

    except Exception as e:
        connection.rollback()
        try:
            current_app.logger.exception("Error updating admission status")
        except Exception:
            print("Error updating admission status:", e)
        flash(f"Database error: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('admissions_blueprint.admission_list'))



    

@blueprint.route('/bulk_update_status', methods=['POST'])
def bulk_update_admission_status():
    """
    Approve multiple admissions selected from the UI.

    Flow:
      1. Read admission_ids[] from the form and validate/convert to ints.
      2. Lock the corresponding admissions rows (FOR UPDATE) and ensure they are Pending.
      3. For each admission:
         - Ensure it has a linked pupils_admission record.
         - Ensure the applicant's reg_no doesn't already exist in pupils.
      4. If any validation errors, rollback and show a combined error flash.
      5. Otherwise insert each applicant into pupils and update admissions.admission_status = 'Approved'.
      6. Commit and flash success.
    """
    ids = request.form.getlist('admission_ids[]') or request.form.getlist('admission_ids')
    if not ids:
        flash("No applications selected.", "warning")
        return redirect(url_for('admissions_blueprint.admission_list'))

    # Validate and convert to integers
    try:
        admission_ids = tuple(int(x) for x in ids)
    except ValueError:
        flash("Invalid application IDs provided.", "danger")
        return redirect(url_for('admissions_blueprint.admission_list'))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        connection.start_transaction()

        # Lock and fetch selected admissions that are still Pending
        placeholders = ','.join(['%s'] * len(admission_ids))
        cursor.execute(f"""
            SELECT *
            FROM admissions
            WHERE admission_id IN ({placeholders})
              AND admission_status = 'Pending'
            FOR UPDATE
        """, admission_ids)
        admissions = cursor.fetchall()

        if not admissions:
            flash("No pending applications found for the selected items.", "info")
            connection.rollback()
            return redirect(url_for('admissions_blueprint.admission_list'))

        # Validate each admission and prepare list to insert
        to_process = []
        errors = []

        # Build a set of reg_nos we will insert to detect duplicates among selected rows
        regnos_being_inserted = set()

        for adm in admissions:
            admission_id = adm['admission_id']
            src_pupil_id = adm.get('pupil_id')
            if not src_pupil_id:
                errors.append(f"Admission {admission_id}: no linked applicant record.")
                continue

            # Lock and fetch applicant data
            cursor.execute("""
                SELECT *
                FROM pupils_admission
                WHERE pupil_id = %s
                FOR UPDATE
            """, (src_pupil_id,))
            applicant = cursor.fetchone()
            if not applicant:
                errors.append(f"Admission {admission_id}: applicant details not found.")
                continue

            reg_no = (applicant.get('reg_no') or "").strip()
            if reg_no:
                # Check for existing reg_no in pupils
                cursor.execute("SELECT pupil_id FROM pupils WHERE reg_no = %s", (reg_no,))
                if cursor.fetchone():
                    errors.append(f"Admission {admission_id}: reg_no '{reg_no}' already exists in pupils.")
                    continue

                # Check duplicates among this batch
                if reg_no in regnos_being_inserted:
                    errors.append(f"Admission {admission_id}: duplicate reg_no '{reg_no}' in selected applications.")
                    continue

                regnos_being_inserted.add(reg_no)

            # All good for this applicant
            to_process.append((adm, applicant))

        if errors:
            # Validation failed for one or more items — rollback and report
            connection.rollback()
            flash("Bulk approval aborted: " + " ".join(errors), "danger")
            return redirect(url_for('admissions_blueprint.admission_list'))

        # Perform inserts and updates
        approved_count = 0
        for adm, applicant in to_process:
            # Build INSERT values in the same order as pupils table
            values = (
                applicant.get('guardian_id'),
                applicant.get('reg_no'),
                applicant.get('index_number'),
                applicant.get('nin_number'),
                applicant.get('home_district'),
                applicant.get('emis_number'),
                applicant.get('dorm_id'),
                applicant.get('first_name'),
                applicant.get('other_name'),
                applicant.get('last_name'),
                applicant.get('image'),
                applicant.get('date_of_birth'),
                applicant.get('gender'),
                applicant.get('nationality'),
                applicant.get('languages_spoken'),
                applicant.get('stream_id'),
                applicant.get('class_id'),
                applicant.get('admission_date'),
                applicant.get('year_id'),
                applicant.get('term_id'),
                applicant.get('address'),
                applicant.get('emergency_contact'),
                applicant.get('medical_info'),
                applicant.get('special_needs'),
                applicant.get('prev_school_name'),
                applicant.get('reason_for_leaving'),
                applicant.get('attendance_record'),
                applicant.get('academic_performance'),
                applicant.get('notes'),
                applicant.get('residential_status'),
                session.get('user_id')
            )

            cursor.execute("""
                INSERT INTO pupils (
                    guardian_id, reg_no, index_number, nin_number,
                    home_district, emis_number, dorm_id,
                    first_name, other_name, last_name,
                    image, date_of_birth, gender, nationality,
                    languages_spoken, stream_id, class_id,
                    admission_date, year_id, term_id,
                    address, emergency_contact, medical_info,
                    special_needs, prev_school_name, reason_for_leaving,
                    attendance_record, academic_performance,
                    notes, residential_status, created_by
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s
                )
            """, values)

            # Update admissions.admission_status to Approved
            cursor.execute("""
                UPDATE admissions
                SET admission_status = 'Approved'
                WHERE admission_id = %s
            """, (adm['admission_id'],))

            approved_count += 1

        connection.commit()
        flash(f"{approved_count} application(s) approved successfully.", "success")

    except Exception as e:
        connection.rollback()
        try:
            current_app.logger.exception("Bulk approval error")
        except Exception:
            print("Bulk approval error:", e)
        flash(f"Bulk approval failed: {str(e)}", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('admissions_blueprint.admission_list'))






    
@blueprint.route('/<template>')
def route_template(template):
    try:
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)
        return render_template("admissions/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('admissions/page-404.html'), 404
    except Exception as e:
        logger.error(f"Template Route Error: {e}")
        return render_template('admissions/page-500.html'), 500

def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'admissions'
        return segment
    except Exception:
        return None