# Standard Library
import os
import re
import random
import logging
from datetime import datetime

# Third-Party
import mysql.connector
from mysql.connector import Error
from werkzeug.utils import secure_filename
from jinja2 import TemplateNotFound

# Flask
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, current_app
)

# Internal Modules
from apps import get_db_connection
from apps.gen_ids import blueprint




# Start of gen_id handling
@blueprint.route('/gen_ids')
def gen_ids_():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            -- Pupil Info
            p.pupil_id AS pupil_id,
            p.reg_no,
            p.first_name AS pupil_first_name,
            p.other_name AS pupil_other_name,
            p.last_name AS pupil_last_name,
            p.gender, 
            p.date_of_birth,
            p.class_id,
            p.year_id,
            p.image AS pupil_image,

            -- Father's Info
            f.first_name AS father_first_name,
            f.other_name AS father_other_name,
            f.last_name AS father_last_name,
            f.image AS father_image,
            f.sign_image AS father_sign,

            -- Mother's Info
            m.first_name AS mother_first_name,
            m.other_name AS mother_other_name,
            m.last_name AS mother_last_name,
            m.image AS mother_image,
            m.sign_image AS mother_sign,

            -- Guardian's Info
            g.first_name AS guardian_first_name,
            g.other_name AS guardian_other_name,
            g.last_name AS guardian_last_name,
            g.relationship,
            g.contact_number,
            g.image AS guardian_image,
            g.sign_image AS guardian_sign,

            -- Class Info
            c.class_id,
            c.year,
            c.teacher_in_charge,
            c.room_number

        FROM pupils p
        LEFT JOIN fathers f ON p.pupil_id = f.pupil_id
        LEFT JOIN mothers m ON p.pupil_id = m.pupil_id
        LEFT JOIN guardians g ON p.pupil_id = g.pupil_id
        LEFT JOIN classes c ON p.class_id = c.class_id
    """)

    gen_id = cursor.fetchall()
    cursor.close()
    connection.close()

    return render_template('gen_ids/gen_ids.html', gen_id=gen_id, segment='gen_ids')











import qrcode
import os
from flask import send_file

@blueprint.route('/generate_id_card/<int:pupil_id>', methods=['GET', 'POST'])
def generate_id_card(pupil_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            -- Pupil Info
            p.pupil_id AS pupil_id,
            p.reg_no,
            p.first_name AS pupil_first_name,
            p.other_name AS pupil_other_name,
            p.last_name AS pupil_last_name,
            p.gender, 
            p.date_of_birth,
            p.class_id,
            p.year_id,
            p.image AS pupil_image,

            -- Father's Info
            f.first_name AS father_first_name,
            f.other_name AS father_other_name,
            f.last_name AS father_last_name,
            f.image AS father_image,
            f.sign_image AS father_sign,

            -- Mother's Info
            m.first_name AS mother_first_name,
            m.other_name AS mother_other_name,
            m.last_name AS mother_last_name,
            m.image AS mother_image,
            m.sign_image AS mother_sign,

            -- Guardian's Info
            g.first_name AS guardian_first_name,
            g.other_name AS guardian_other_name,
            g.last_name AS guardian_last_name,
            g.relationship,
            g.contact_number,
            g.image AS guardian_image,
            g.sign_image AS guardian_sign,

            -- Class Info
            c.class_id,
            c.year,
            c.teacher_in_charge,
            c.room_number,
            c.class_name

        FROM pupils p
        LEFT JOIN fathers f ON p.pupil_id = f.pupil_id
        LEFT JOIN mothers m ON p.pupil_id = m.pupil_id
        LEFT JOIN guardians g ON p.pupil_id = g.pupil_id
        LEFT JOIN classes c ON p.class_id = c.class_id
        WHERE p.pupil_id = %s
    """, (pupil_id,))
    
    data = cursor.fetchone()

    cursor.close()
    connection.close()

    if not data:
        flash("ID card data not found.", "danger")
        return redirect(url_for('gen_ids_blueprint.gen_ids'))

    # Create QR code that links to the pupil's profile or has encoded data
    qr_data = f"https://yourdomain.com/pupil_profile/{pupil_id}"
    qr_img = qrcode.make(qr_data)
    
    qr_filename = f"qr_{pupil_id}.png"

    qr_path = os.path.join(current_app.config['UPLOAD_FOLDER'], qr_filename)
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    qr_img.save(qr_path)

    # Attach QR path to data
    data['qr_code'] = qr_filename

    return render_template('gen_ids/id_card.html', data=data)






    

# Dynamic route for rendering other templates
@blueprint.route('/<template>')
def route_template(template):
    try:
        # Ensure the template ends with '.html' for correct render
        if not template.endswith('.html'):
            template += '.html'

        segment = get_segment(request)

        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except Exception as e:
        return render_template('home/page-500.html'), 500


def get_segment(request):
    """Extracts the last part of the URL path to identify the current page."""
    try:
        segment = request.path.split('/')[-1]
        if segment == '':
            segment = 'gen_ids'
        return segment

    except Exception as e:
        return None
