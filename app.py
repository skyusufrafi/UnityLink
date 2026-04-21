import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- GOOGLE SHEETS SETUP ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_raw = os.environ.get('GOOGLE_CREDENTIALS')

try:
    if creds_raw:
        creds_info = json.loads(creds_raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    
    client = gspread.authorize(creds)
    SHEET_ID = "11k63x80AQ9mkUjpyHe1QXqum4mreNGOfWwCA7gjysao"
    sheet = client.open_by_key(SHEET_ID).sheet1
except Exception as e:
    print(f"Database Connection Error: {e}")

# --- AUTO-CLEAN LOGIC ---
def clean_database():
    try:
        # get_all_values() zyada fast hota hai cleaning ke liye
        rows = sheet.get_all_values()
        if len(rows) <= 1: # Sirf header hai ya sheet khali hai
            return

        header = rows[0]
        data_rows = rows[1:]

        unique_records = {}
        # Header indexes nikalna (Contact, Role, HelpType)
        try:
            contact_idx = header.index("Contact")
            role_idx = header.index("Role")
            help_idx = header.index("HelpType")
        except ValueError:
            print("Headers missing in Sheet!")
            return

        for row in data_rows:
            # Clean data for key generation
            contact = str(row[contact_idx]).replace(" ", "").strip()
            role = str(row[role_idx]).strip()
            h_type = str(row[help_idx]).strip().title()
            
            # Key: Unique combination
            key = f"{contact}-{role}-{h_type}"
            unique_records[key] = row

        # Final rows taiyar karein
        clean_rows = [header] + list(unique_records.values())

        # Sheet update: Clear and Update
        sheet.clear()
        # Vercel/gspread naya syntax compatible
        sheet.update('A1', clean_rows)
        print("Database Auto-Cleaned!")
    except Exception as e:
        print(f"Auto-clean Error: {e}")

# --- ROUTES ---
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/user')
def user_page():
    clean_database() # Trigger on button click
    return render_template('user.html')

@app.route('/volunteer')
def volunteer_page():
    clean_database() # Trigger on button click
    return render_template('volunteer.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json
        user_name = str(data.get('name')).strip().title()
        user_contact = str(data.get('contact')).replace(" ", "").strip()
        user_pin = int(data.get('pincode'))
        user_role = str(data.get('role')).strip()
        user_help = str(data.get('helpType')).strip().title()

        all_records = sheet.get_all_records()
        
        # --- SEPARATE DUPLICATE CHECK BEFORE INSERT ---
        already_exists = False
        for record in all_records:
            db_contact = str(record.get('Contact')).replace(" ", "").strip()
            db_role = str(record.get('Role')).strip()
            if db_contact == user_contact and db_role == user_role:
                already_exists = True
                break

        if not already_exists:
            new_row = [user_name, user_help, user_contact, user_pin, user_role]
            sheet.append_row(new_row)
            status_msg = "success"
        else:
            status_msg = "already_existed"
        
        # --- MATCHING LOGIC ---
        all_records = sheet.get_all_records()
        matches = []
        opposite_role = "Volunteer" if user_role == "User" else "User"
        
        seen_contacts = set()
        for record in all_records:
            db_role = str(record.get('Role')).strip()
            db_help = str(record.get('HelpType')).strip().title()
            db_contact = str(record.get('Contact')).strip()

            if db_role == opposite_role and db_help == user_help and db_contact not in seen_contacts:
                try:
                    db_pin = int(record.get('PinCode', 0))
                    distance = abs(user_pin - db_pin)
                    record['distance'] = distance
                    matches.append(record)
                    seen_contacts.add(db_contact)
                except:
                    continue
        
        matches = sorted(matches, key=lambda x: x.get('distance', 9999))
        
        return jsonify({"status": "success", "message": status_msg, "matches": matches})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
