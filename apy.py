from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import webbrowser

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_NAME = 'dormfinder.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table updated with phone, address, and bio columns
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            bio TEXT
        )
    ''')
    
    # Properties table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_email TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            address TEXT NOT NULL,
            barangay TEXT NOT NULL,
            raw_rent TEXT NOT NULL,
            rent TEXT NOT NULL,
            total_rooms TEXT NOT NULL,
            avail_rooms TEXT NOT NULL,
            occupied TEXT NOT NULL,
            description TEXT,
            rules TEXT,
            amenities TEXT,
            image TEXT,
            FOREIGN KEY (owner_email) REFERENCES users (email)
        )
    ''')
    
    # Bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            property_name TEXT NOT NULL,
            room_name TEXT NOT NULL,
            student_name TEXT NOT NULL,
            student_email TEXT NOT NULL,
            owner_email TEXT NOT NULL,
            move_in_date TEXT NOT NULL,
            message TEXT,
            rent TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES properties (id),
            FOREIGN KEY (student_email) REFERENCES users (email),
            FOREIGN KEY (owner_email) REFERENCES users (email)
        )
    ''')

    # Messages table (for the split-screen conversation inbox)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            property_name TEXT,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            receiver_email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def serve_homepage():
    return send_from_directory('.', 'index.html')

@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json
    fullname = data.get('fullname', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'student')

    if not fullname or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    hashed_password = generate_password_hash(password)

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (fullname, email, password, role, phone, address, bio) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (fullname, email, hashed_password, role, '', '', '')
        )
        conn.commit()
        conn.close()
        return jsonify({
            'success': True, 
            'message': 'Account created successfully!',
            'user': {'name': fullname, 'email': email, 'role': role, 'phone': '', 'address': '', 'bio': ''}
        })
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Email already exists. Please sign in.'}), 400

@app.route('/api/signin', methods=['POST'])
def api_signin():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # Demo accounts - no database needed
    demo_accounts = {
        'demostudent@gmail.com': {'password': 'demo123', 'role': 'student', 'name': 'Demo Student'},
        'demoowner@gmail.com': {'password': 'demo123', 'role': 'owner', 'name': 'Demo Owner'}
    }
    
    if email in demo_accounts:
        if demo_accounts[email]['password'] == password:
            return jsonify({
                'success': True,
                'user': {
                    'name': demo_accounts[email]['name'],
                    'email': email,
                    'role': demo_accounts[email]['role'],
                    'phone': '',
                    'address': '',
                    'bio': '',
                    'isDemo': True
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401

    # Admin account
    if email == 'admin@dormfinder.com' and password == 'admin123':
        return jsonify({
            'success': True,
            'user': {'name': 'System Administrator', 'email': email, 'role': 'admin', 'phone': '', 'address': '', 'bio': ''}
        })

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT fullname, email, password, role, phone, address, bio FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    conn.close()

    if row and check_password_hash(row[2], password):
        return jsonify({
            'success': True,
            'user': {
                'name': row[0],
                'email': row[1],
                'role': row[3],
                'phone': row[4] or '',
                'address': row[5] or '',
                'bio': row[6] or ''
            }
        })
    
    return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401

@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    data = request.json
    email = data.get('email', '').strip().lower()
    new_fullname = data.get('fullname', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()
    bio = data.get('bio', '').strip()

    if not email or not new_fullname:
        return jsonify({'success': False, 'message': 'Email and full name are required.'}), 400

    # Demo accounts - just show success without saving to DB
    if email in ['demostudent@gmail.com', 'demoowner@gmail.com']:
        return jsonify({
            'success': True,
            'message': 'Demo: Profile updated successfully! (No database save in demo mode)',
            'user': {
                'name': new_fullname,
                'email': email,
                'role': 'student' if email == 'demostudent@gmail.com' else 'owner',
                'phone': phone,
                'address': address,
                'bio': bio,
                'isDemo': True
            }
        })

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET fullname = ?, phone = ?, address = ?, bio = ? 
            WHERE email = ?
        ''', (new_fullname, phone, address, bio, email))
        conn.commit()

        cursor.execute('SELECT fullname, email, role, phone, address, bio FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'success': False, 'message': 'User not found.'}), 404

        return jsonify({
            'success': True,
            'message': 'Profile updated successfully!',
            'user': {
                'name': row[0],
                'email': row[1],
                'role': row[2],
                'phone': row[3] or '',
                'address': row[4] or '',
                'bio': row[5] or ''
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ── PROPERTY APIs ──────────────────────────────────────────
@app.route('/api/properties', methods=['GET'])
def get_properties():
    owner_email = request.args.get('email', '').strip().lower()
    
    # Demo properties available to all users (for students to browse)
    demo_properties = [
        {
            'id': 1,
            'owner_email': 'demoowner@gmail.com',
            'owner_name': 'Demo Owner',
            'name': 'Demo Dorm - Minglanilla Heights',
            'type': 'dormitory',
            'address': '123 Main St',
            'barangay': 'Minglanilla',
            'rawRent': '₱5,000',
            'rent': '5000',
            'totalRooms': '20',
            'availRooms': '8',
            'occupied': '12',
            'desc': 'This is a demo dormitory showcasing the property listing features. Located in the heart of Minglanilla near campus.',
            'rules': 'No smoking, No pets, Quiet hours 10PM-8AM',
            'amenities': ['Wi-Fi', 'Common Room', 'Kitchen', 'Laundry'],
            'image': 'https://images.unsplash.com/photo-1544716278-ca5e3af4abd8?w=500&h=300&fit=crop'
        },
        {
            'id': 2,
            'owner_email': 'demoowner@gmail.com',
            'owner_name': 'Demo Owner',
            'name': 'Demo Boarding House - Poblacion',
            'type': 'boarding house',
            'address': '456 Poblacion Ave',
            'barangay': 'Poblacion',
            'rawRent': '₱4,500',
            'rent': '4500',
            'totalRooms': '15',
            'availRooms': '3',
            'occupied': '12',
            'desc': 'A cozy boarding house perfect for students. Close to shops and restaurants in Poblacion area.',
            'rules': 'Curfew at 11PM, No visitors after 9PM',
            'amenities': ['Wi-Fi', 'Parking', 'Hot Water', 'Study Area'],
            'image': 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=500&h=300&fit=crop'
        },
        {
            'id': 3,
            'owner_email': 'demoowner@gmail.com',
            'owner_name': 'Demo Owner',
            'name': 'Demo Student Apartments - Calajo-an',
            'type': 'apartment',
            'address': '789 Calajo-an Street',
            'barangay': 'Calajo-an',
            'rawRent': '₱6,000',
            'rent': '6000',
            'totalRooms': '12',
            'availRooms': '5',
            'occupied': '7',
            'desc': 'Modern apartments with all amenities. Perfect for groups of students. Features spacious rooms and modern facilities.',
            'rules': 'No loud noise after 10PM, Shared spaces must be kept clean',
            'amenities': ['Wi-Fi', 'Gym', 'CCTV', 'Water Tank', 'Parking', 'Generator'],
            'image': 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=500&h=300&fit=crop'
        }
    ]
    
    # If requesting for owner's own properties
    if owner_email == 'demoowner@gmail.com':
        return jsonify({'success': True, 'properties': demo_properties})
    
    # Demo student gets to see all demo properties (to browse and book)
    if owner_email == 'demostudent@gmail.com':
        return jsonify({'success': True, 'properties': demo_properties})
    
    # No email parameter - return all demo properties (for public browse)
    if not owner_email:
        return jsonify({'success': True, 'properties': demo_properties})
    
    # Regular user - query from database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = '''
        SELECT p.id, p.owner_email, u.fullname, p.name, p.type, p.address, p.barangay, 
               p.raw_rent, p.rent, p.total_rooms, p.avail_rooms, p.occupied, 
               p.description, p.rules, p.amenities, p.image 
        FROM properties p
        LEFT JOIN users u ON p.owner_email = u.email
    '''
    
    if owner_email:
        cursor.execute(query + ' WHERE p.owner_email = ?', (owner_email,))
    else:
        cursor.execute(query)
    
    rows = cursor.fetchall()
    conn.close()

    props = []
    for r in rows:
        props.append({
            'id': r[0],
            'owner_email': r[1],
            'owner_name': r[2] if r[2] else 'Property Owner',
            'name': r[3],
            'type': r[4],
            'address': r[5],
            'barangay': r[6],
            'rawRent': r[7],
            'rent': r[8],
            'totalRooms': r[9],
            'availRooms': r[10],
            'occupied': r[11],
            'desc': r[12],
            'rules': r[13],
            'amenities': r[14].split(',') if r[14] else [],
            'image': r[15]
        })
    return jsonify({'success': True, 'properties': props})

@app.route('/api/properties', methods=['POST'])
def save_property():
    data = request.json
    owner_email = data.get('owner_email', '').strip().lower()
    prop_id = data.get('id')

    if not owner_email:
        return jsonify({'success': False, 'message': 'Owner email required.'}), 400

    # Demo accounts - just show success without saving to DB
    if owner_email == 'demoowner@gmail.com':
        return jsonify({'success': True, 'message': 'Demo: Property saved successfully! (No database save in demo mode)'})

    name = data.get('name')
    ptype = data.get('type')
    address = data.get('address')
    barangay = data.get('barangay')
    raw_rent = data.get('rawRent')
    rent = data.get('rent')
    total_rooms = data.get('totalRooms')
    avail_rooms = data.get('availRooms')
    occupied = data.get('occupied')
    desc = data.get('desc')
    rules = data.get('rules')
    amenities = ','.join(data.get('amenities', []))
    image = data.get('image')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if prop_id:
        cursor.execute('''
            UPDATE properties SET name=?, type=?, address=?, barangay=?, raw_rent=?, rent=?, total_rooms=?, avail_rooms=?, occupied=?, description=?, rules=?, amenities=?, image=?
            WHERE id=? AND owner_email=?
        ''', (name, ptype, address, barangay, raw_rent, rent, total_rooms, avail_rooms, occupied, desc, rules, amenities, image, prop_id, owner_email))
    else:
        cursor.execute('''
            INSERT INTO properties (owner_email, name, type, address, barangay, raw_rent, rent, total_rooms, avail_rooms, occupied, description, rules, amenities, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (owner_email, name, ptype, address, barangay, raw_rent, rent, total_rooms, avail_rooms, occupied, desc, rules, amenities, image))

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Property saved successfully!'})

@app.route('/api/properties/<int:prop_id>', methods=['DELETE'])
def delete_property(prop_id):
    owner_email = request.args.get('email', '').strip().lower()
    
    # Demo accounts - just show success without saving to DB
    if owner_email == 'demoowner@gmail.com':
        return jsonify({'success': True, 'message': 'Demo: Property deleted successfully! (No database change in demo mode)'})
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM properties WHERE id = ?', (prop_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Property deleted successfully!'})

# ── BOOKING APIs ──────────────────────────────────────────
@app.route('/api/bookings', methods=['POST'])
def create_booking():
    data = request.json
    property_id = data.get('property_id')
    property_name = data.get('property_name')
    room_name = data.get('room_name')
    student_name = data.get('student_name')
    student_email = data.get('student_email', '').strip().lower()
    owner_email = data.get('owner_email', '').strip().lower()
    move_in_date = data.get('move_in_date')
    message = data.get('message', '')
    rent = data.get('rent')

    if not property_id or not student_email or not owner_email or not move_in_date:
        return jsonify({'success': False, 'message': 'Missing required booking details.'}), 400

    # Demo accounts - just show success message without saving to DB
    if student_email == 'demostudent@gmail.com' or owner_email == 'demoowner@gmail.com':
        return jsonify({'success': True, 'message': 'Demo: Booking request submitted successfully! (No database save in demo mode)'})

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bookings (property_id, property_name, room_name, student_name, student_email, owner_email, move_in_date, message, rent, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (property_id, property_name, room_name, student_name, student_email, owner_email, move_in_date, message, rent))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Booking request submitted successfully!'})

@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    student_email = request.args.get('student_email', '').strip().lower()
    owner_email = request.args.get('owner_email', '').strip().lower()

    # Demo student - return sample bookings
    if student_email == 'demostudent@gmail.com':
        demo_bookings = [
            {
                'id': 1,
                'property_name': 'Demo Dorm - Minglanilla Heights',
                'room_name': 'Room 101',
                'student_name': 'Demo Student',
                'move_in_date': '2026-01-15',
                'message': 'This is a demo booking request',
                'rent': '₱5,000',
                'status': 'pending',
                'created_at': '2026-01-01 10:00:00'
            }
        ]
        return jsonify({'success': True, 'bookings': demo_bookings})

    # Demo owner - return sample bookings from students
    if owner_email == 'demoowner@gmail.com':
        demo_owner_bookings = [
            {
                'id': 1,
                'property_name': 'Demo Dorm - Minglanilla Heights',
                'room_name': 'Room 101',
                'student_name': 'John Student',
                'student_email': 'john@example.com',
                'move_in_date': '2026-01-15',
                'message': 'Interested in booking this room',
                'rent': '₱5,000',
                'status': 'pending',
                'created_at': '2026-01-01 10:00:00'
            },
            {
                'id': 2,
                'property_name': 'Demo Boarding House - Poblacion',
                'room_name': 'Room 205',
                'student_name': 'Maria Santos',
                'student_email': 'maria@example.com',
                'move_in_date': '2026-02-01',
                'message': 'Can I visit the room first?',
                'rent': '₱4,500',
                'status': 'approved',
                'created_at': '2025-12-28 14:30:00'
            }
        ]
        return jsonify({'success': True, 'bookings': demo_owner_bookings})

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if student_email:
        cursor.execute('''
            SELECT id, property_name, room_name, student_name, move_in_date, message, rent, status, created_at 
            FROM bookings WHERE student_email = ? ORDER BY id DESC
        ''', (student_email,))
    elif owner_email:
        cursor.execute('''
            SELECT id, property_name, room_name, student_name, student_email, move_in_date, message, rent, status, created_at 
            FROM bookings WHERE owner_email = ? ORDER BY id DESC
        ''', (owner_email,))
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Email parameters required.'}), 400

    rows = cursor.fetchall()
    conn.close()

    bookings = []
    for r in rows:
        if student_email:
            bookings.append({
                'id': r[0],
                'property_name': r[1],
                'room_name': r[2],
                'student_name': r[3],
                'move_in_date': r[4],
                'message': r[5],
                'rent': r[6],
                'status': r[7],
                'created_at': r[8]
            })
        else:
            bookings.append({
                'id': r[0],
                'property_name': r[1],
                'room_name': r[2],
                'student_name': r[3],
                'student_email': r[4],
                'move_in_date': r[5],
                'message': r[6],
                'rent': r[7],
                'status': r[8],
                'created_at': r[9]
            })

    return jsonify({'success': True, 'bookings': bookings})

@app.route('/api/bookings/<int:booking_id>/status', methods=['POST'])
def update_booking_status(booking_id):
    data = request.json
    new_status = data.get('status')

    if new_status not in ['approved', 'rejected']:
        return jsonify({'success': False, 'message': 'Invalid status.'}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE bookings SET status = ? WHERE id = ?', (new_status, booking_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': f'Booking request {new_status}!'})

# ── MESSAGING APIs ────────────────────────────────────────
@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.json
    property_id = data.get('property_id')
    property_name = data.get('property_name', 'General Inquiry')
    sender_email = data.get('sender_email', '').strip().lower()
    sender_name = data.get('sender_name', 'User')
    receiver_email = data.get('receiver_email', '').strip().lower()
    message = data.get('message', '').strip()

    if not sender_email or not receiver_email or not message:
        return jsonify({'success': False, 'message': 'Missing required message fields.'}), 400

    # Demo accounts - just show success without saving to DB
    if sender_email in ['demostudent@gmail.com', 'demoowner@gmail.com'] or receiver_email in ['demostudent@gmail.com', 'demoowner@gmail.com']:
        return jsonify({'success': True, 'message': 'Demo: Message sent successfully! (No database save in demo mode)'})

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (property_id, property_name, sender_email, sender_name, receiver_email, message)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (property_id, property_name, sender_email, sender_name, receiver_email, message))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'Message sent successfully!'})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    user_email = request.args.get('email', '').strip().lower()
    if not user_email:
        return jsonify({'success': False, 'message': 'Email parameter required.'}), 400

    # Demo student - return sample messages
    if user_email == 'demostudent@gmail.com':
        demo_messages = [
            {
                'id': 1,
                'property_id': 1,
                'property_name': 'Demo Dorm - Minglanilla Heights',
                'sender_email': 'demoowner@gmail.com',
                'sender_name': 'Demo Owner',
                'receiver_email': 'demostudent@gmail.com',
                'message': 'Hi! Thanks for your interest in our dorm. Please let me know if you have any questions!',
                'created_at': '2026-01-02 09:00:00'
            },
            {
                'id': 2,
                'property_id': 1,
                'property_name': 'Demo Dorm - Minglanilla Heights',
                'sender_email': 'demostudent@gmail.com',
                'sender_name': 'Demo Student',
                'receiver_email': 'demoowner@gmail.com',
                'message': 'Yes, I would like to schedule a viewing. When are you available?',
                'created_at': '2026-01-02 10:15:00'
            }
        ]
        return jsonify({'success': True, 'messages': demo_messages})

    # Demo owner - return sample messages
    if user_email == 'demoowner@gmail.com':
        demo_messages = [
            {
                'id': 1,
                'property_id': 1,
                'property_name': 'Demo Dorm - Minglanilla Heights',
                'sender_email': 'demostudent@gmail.com',
                'sender_name': 'Demo Student',
                'receiver_email': 'demoowner@gmail.com',
                'message': 'Hi! I am interested in booking a room at your dorm.',
                'created_at': '2026-01-02 08:30:00'
            },
            {
                'id': 2,
                'property_id': 1,
                'property_name': 'Demo Dorm - Minglanilla Heights',
                'sender_email': 'demoowner@gmail.com',
                'sender_name': 'Demo Owner',
                'receiver_email': 'demostudent@gmail.com',
                'message': 'Welcome! I would love to help you find the perfect room.',
                'created_at': '2026-01-02 09:00:00'
            }
        ]
        return jsonify({'success': True, 'messages': demo_messages})

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, property_id, property_name, sender_email, sender_name, receiver_email, message, created_at
        FROM messages 
        WHERE sender_email = ? OR receiver_email = ?
        ORDER BY created_at ASC
    ''', (user_email, user_email))
    rows = cursor.fetchall()
    conn.close()

    msgs = []
    for r in rows:
        msgs.append({
            'id': r[0],
            'property_id': r[1],
            'property_name': r[2],
            'sender_email': r[3],
            'sender_name': r[4],
            'receiver_email': r[5],
            'message': r[6],
            'created_at': r[7]
        })
    return jsonify({'success': True, 'messages': msgs})

if __name__ == '__main__':
    init_db()
    webbrowser.open_new('http://127.0.0.1:5000/')
    print('Starting Dorm Finder database server...')
    app.run(host='127.0.0.1', port=5000, debug=True)