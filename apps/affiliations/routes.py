import pytz
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from jinja2 import TemplateNotFound

from apps import get_db_connection
from apps.affiliations import blueprint


# --- Helpers ---

def get_kampala_time():
    return datetime.now(pytz.timezone("Africa/Kampala"))


def get_segment(request):
    try:
        segment = request.path.split('/')[-1]
        return segment if segment != '' else 'manage_affiliations'
    except:
        return None


# ---------------------------------------------------------
# Manage Affiliations
# ---------------------------------------------------------






@blueprint.route('/manage_affiliations')
def manage_affiliations():

    try:
        with get_db_connection() as connection:
            with connection.cursor(dictionary=True) as cursor:

                # =========================
                # STATISTICS
                # =========================
                cursor.execute("""
                    SELECT 
                        COUNT(id) AS total_affiliations,
                        SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) AS active_count,
                        COUNT(DISTINCT country) AS total_countries
                    FROM affiliations
                """)
                stats = cursor.fetchone() or {
                    "total_affiliations": 0,
                    "active_count": 0,
                    "total_countries": 0
                }

                # =========================
                # AFFILIATION LIST
                # =========================
                cursor.execute("""
                    SELECT *
                    FROM affiliations
                    ORDER BY created_at DESC
                """)
                affiliations = cursor.fetchall()

        return render_template(
            "affiliations/affiliation_list.html",
            stats=stats,
            affiliations=affiliations,
            segment="manage_affiliations"
        )

    except Exception as e:
        flash(f"Error loading affiliation data: {str(e)}", "danger")
        return redirect(url_for('home_blueprint.index'))









# ---------------------------------------------------------
# Add Affiliation
# ---------------------------------------------------------

@blueprint.route('/add_affiliation', methods=['POST'])
def add_affiliation():

    name = request.form.get("name", "").strip()
    type = request.form.get("type", "").strip()
    acronym = request.form.get("acronym")
    country = request.form.get("country", "Uganda")
    registration_number = request.form.get("registration_number")
    contact_email = request.form.get("contact_email")
    phone_number = request.form.get("phone_number")
    website_url = request.form.get("website_url")
    physical_address = request.form.get("physical_address")

    if not name or not type:
        flash("Affiliation Name and Type are required.", "warning")
        return redirect(url_for("affiliations_blueprint.manage_affiliations"))

    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO affiliations
            (name, type, acronym, country, registration_number,
             contact_email, phone_number, website_url, physical_address, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Active')
        """, (
            name, type, acronym, country, registration_number,
            contact_email, phone_number, website_url, physical_address
        ))

        connection.commit()
        flash(f"{name} affiliation registered successfully.", "success")

    except Exception as e:
        connection.rollback()
        flash(f"Database Error: {str(e)}", "danger")

    finally:
        connection.close()

    return redirect(url_for("affiliations_blueprint.manage_affiliations"))


# ---------------------------------------------------------
# Edit Affiliation
# ---------------------------------------------------------

@blueprint.route('/edit_affiliation/<int:affiliation_id>', methods=['POST'])
def edit_affiliation(affiliation_id):

    name = request.form.get("name")
    type = request.form.get("type")
    acronym = request.form.get("acronym")
    country = request.form.get("country")
    registration_number = request.form.get("registration_number")
    contact_email = request.form.get("contact_email")
    phone_number = request.form.get("phone_number")
    website_url = request.form.get("website_url")
    physical_address = request.form.get("physical_address")
    status = request.form.get("status")

    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE affiliations
            SET
                name=%s,
                type=%s,
                acronym=%s,
                country=%s,
                registration_number=%s,
                contact_email=%s,
                phone_number=%s,
                website_url=%s,
                physical_address=%s,
                status=%s
            WHERE id=%s
        """, (
            name, type, acronym, country,
            registration_number, contact_email,
            phone_number, website_url,
            physical_address, status,
            affiliation_id
        ))

        connection.commit()
        flash(f"Affiliation '{name}' updated successfully.", "success")

    except Exception as e:
        connection.rollback()
        flash(f"Error updating affiliation: {str(e)}", "danger")

    finally:
        connection.close()

    return redirect(url_for("affiliations_blueprint.manage_affiliations"))


# ---------------------------------------------------------
# Delete Affiliation
# ---------------------------------------------------------

@blueprint.route('/delete_affiliation/<int:affiliation_id>', methods=['POST'])
def delete_affiliation(affiliation_id):

    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM affiliations WHERE id=%s",
            (affiliation_id,)
        )

        connection.commit()

        if cursor.rowcount > 0:
            flash("Affiliation removed successfully.", "success")
        else:
            flash("Affiliation not found.", "warning")

    except Exception as e:
        connection.rollback()
        flash("Cannot delete affiliation. It may be referenced elsewhere.", "danger")

    finally:
        connection.close()

    return redirect(url_for("affiliations_blueprint.manage_affiliations"))


# ---------------------------------------------------------
# Generic Routing
# ---------------------------------------------------------

@blueprint.route('/<template>')
def route_template(template):

    try:

        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        return render_template(
            f"affiliations/{template}",
            segment=segment
        )

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404
    except Exception:
        return render_template('home/page-500.html'), 500
