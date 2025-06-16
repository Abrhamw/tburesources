import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, func, and_, or_
from datetime import datetime, date
import sqlite3
import json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'fleet_management_secret_key'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'fleet.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# GPS coordinates for Ethiopian cities (approximate)
ETHIOPIAN_CITIES_GPS = {
    "Addis Ababa": (9.005401, 38.763611),
    "Dire Dawa": (9.589229, 41.870190),
    "Mekelle": (13.496060, 39.476910),
    "Gondar": (12.600000, 37.466667),
    "Hawassa": (7.050000, 38.466667),
    "Bahir Dar": (11.600000, 37.383333),
    "Jimma": (7.666667, 36.833333),
    "Jijiga": (9.350000, 42.800000),
    "Shashamane": (7.200000, 38.600000),
    "Arba Minch": (6.033333, 37.550000),
    "Hosaena": (7.550000, 37.850000),
    "Harar": (9.316667, 42.116667),
    "Dilla": (6.416667, 38.316667),
    "Nekemte": (9.083333, 36.550000),
    "Debre Birhan": (9.683333, 39.533333),
    "Asella": (7.950000, 39.116667),
    "Adama": (8.550000, 39.266667),
    "Wolaita Sodo": (6.850000, 37.750000),
    "Gambela": (8.250000, 34.583333),
    "Debre Markos": (10.333333, 37.733333),
    "Awasa": (7.050000, 38.466667),
    "Bishoftu": (8.750000, 38.983333),
    "Sodo": (6.850000, 37.750000),
    "Adigrat": (14.277778, 39.462500),
    "Axum": (14.121389, 38.723611)
}

# Enums for option fields
VEHICLE_TYPES = ('Pickup', 'Land Cruiser', 'Prado', 'V8', 'Hardtop', 'Minibus', 'Bus', 'Crane', 'ISUZU FSR', 'Other')
FUEL_TYPES = ('Diesel', 'Benzin', 'Hybrid', 'Electric')
ASSIGNMENT_TYPES = ('Program Office I', 'Program Office II', 'Program Office III', 'Program Office IV', 'Central I Region', 'Central II Region', 'Central III Region','North Region','North East I Region','North East II Region','North West Region','West Region','South West Region','South I Region','South II Region','East I Region','East II Region','Region Coordination Office', 'Load Dispatch Center', 'Other')
INSURANCE_TYPES = ('Fully Insured', 'Partial')
SAFETY_TYPES = ('Safe', 'Fair', 'Not Safe')
MAINTENANCE_CENTERS = ('EEP', 'Moenco', 'Other')
YES_NO = ('Yes', 'No')
USER_ROLES = ('admin', 'user')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(Enum(*USER_ROLES, name='user_roles'), default='user')
    last_login = db.Column(db.DateTime)
    
    activities = db.relationship('ActivityLog', backref='user')

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)

class Vehicle(db.Model):
    plate_number = db.Column(db.String(20), primary_key=True)
    chasis = db.Column(db.String(50), unique=True, nullable=False)
    vehicle_type = db.Column(Enum(*VEHICLE_TYPES, name='vehicle_types'))
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    year = db.Column(db.String(4))
    fuel_type = db.Column(Enum(*FUEL_TYPES, name='fuel_types'))
    fuel_capacity = db.Column(db.Float)
    fuel_consumption = db.Column(db.Float)
    loading_capacity = db.Column(db.String(100))
    assigned_for = db.Column(Enum(*ASSIGNMENT_TYPES, name='assignment_types'))
    
    # Relationships
    compliance = db.relationship('Compliance', backref='vehicle', uselist=False)
    maintenance = db.relationship('Maintenance', backref='vehicle')
    assignments = db.relationship('Assignment', backref='vehicle')

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    id_number = db.Column(db.String(50), unique=True)
    phone = db.Column(db.String(15))
    reporting_to = db.Column(db.String(100))
    
    assignments = db.relationship('Assignment', backref='driver')

class Compliance(db.Model):
    plate_number = db.Column(db.String(20), db.ForeignKey('vehicle.plate_number'), primary_key=True)
    insurance_type = db.Column(Enum(*INSURANCE_TYPES, name='insurance_types'))
    insurance_date = db.Column(db.Date)
    yearly_inspection = db.Column(Enum(*YES_NO, name='yes_no_types'))
    inspection_date = db.Column(db.Date)
    safety_audit = db.Column(Enum(*SAFETY_TYPES, name='safety_types'))
    utilization_history = db.Column(db.Text)
    accident_history = db.Column(db.Text)

class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), db.ForeignKey('vehicle.plate_number'))
    last_service_km = db.Column(db.Integer)
    last_service_date = db.Column(db.Date)
    next_service_km = db.Column(db.Integer)
    next_service_date = db.Column(db.Date)
    maintenance_center = db.Column(Enum(*MAINTENANCE_CENTERS, name='maintenance_centers'))
    details = db.Column(db.Text)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), db.ForeignKey('vehicle.plate_number'))
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'))
    work_place = db.Column(db.String(100))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    gps_position = db.Column(db.String(50))
    geofence_violations = db.Column(db.Integer)
    
# Update the get_home_data function
def get_home_data():
    # Vehicle type distribution
    vehicle_types = db.session.query(
        Vehicle.vehicle_type,
        func.count(Vehicle.vehicle_type)
    ).group_by(Vehicle.vehicle_type).all()
    
    # Driver reporting distribution
    driver_reporting = db.session.query(
        Driver.reporting_to,
        func.count(Driver.id)
    ).group_by(Driver.reporting_to).order_by(func.count(Driver.id).desc()).all()
    
    # Assignment distribution
    assignment_distribution = db.session.query(
        Vehicle.assigned_for,
        func.count(Vehicle.assigned_for)
    ).group_by(Vehicle.assigned_for).all()
    
    # Active assignments with GPS positions
    active_assignments = Assignment.query.filter(Assignment.end_date == None).all()
    
    return vehicle_types, driver_reporting, assignment_distribution, active_assignments

def log_activity(user_id, action, details=""):
    log = ActivityLog(user_id=user_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()

def get_dashboard_counts():
    conn = sqlite3.connect('fleet.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM vehicle")
    vehicle_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM driver")
    driver_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM assignment WHERE end_date IS NULL")
    assignment_count = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT v.plate_number, v.make, v.model, m.next_service_date, m.maintenance_center 
        FROM maintenance m
        JOIN vehicle v ON m.plate_number = v.plate_number
        WHERE m.next_service_date <= date('now', '+7 days')
        ORDER BY m.next_service_date
        LIMIT 5
    ''')
    maintenance_due = cursor.fetchall()
    
    cursor.execute('''
        SELECT v.plate_number, v.make, v.model, 
               CASE 
                   WHEN c.yearly_inspection = 'No' THEN 'Inspection Missing'
                   WHEN c.inspection_date < date('now', '-1 year') THEN 'Inspection Expired'
                   WHEN c.insurance_date < date('now', '-1 year') THEN 'Insurance Expired'
                   ELSE 'Unknown Issue'
               END AS issue_type
        FROM compliance c
        JOIN vehicle v ON c.plate_number = v.plate_number
        WHERE c.yearly_inspection = 'No' 
            OR c.inspection_date < date('now', '-1 year')
            OR c.insurance_date < date('now', '-1 year')
        LIMIT 5
    ''')
    compliance_issues = cursor.fetchall()
    
    conn.close()
    
    return vehicle_count, driver_count, assignment_count, maintenance_due, compliance_issues

def convert_city_to_gps(city_name):
    """Convert Ethiopian city name to GPS coordinates"""
    return ETHIOPIAN_CITIES_GPS.get(city_name.title(), (0, 0))

@app.route('/tracking/<plate_number>')
def vehicle_tracking(plate_number):
    vehicle = Vehicle.query.get_or_404(plate_number)
    assignment = Assignment.query.filter_by(plate_number=plate_number, end_date=None).first()
    
    if not assignment:
        flash('No active assignment for this vehicle', 'warning')
        return redirect(url_for('index'))
    
    # Get GPS coordinates
    lat, lng = assignment.gps_position.split(',')
    
    return render_template('tracking.html', 
                           vehicle=vehicle,
                           assignment=assignment,
                           lat=float(lat),
                           lng=float(lng))

@app.before_request
def create_tables():
    db.create_all()
    
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
    
    # Create sample driver if none exist
    if Driver.query.count() == 0:
        driver = Driver(
            name="John Doe",
            id_number="ET-1234567",
            phone="+251911223344",
            reporting_to="Transport Manager"
        )
        db.session.add(driver)
        db.session.commit()

# Update the index route
@app.route('/')
def index():
    counts = get_dashboard_counts()
    vehicle_types, driver_reporting, assignment_distribution, active_assignments = get_home_data()
    
    # Get recent activities
    activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(5).all()
    
    return render_template('index.html', 
                           vehicle_count=counts[0],
                           driver_count=counts[1],
                           assignment_count=counts[2],
                           maintenance_due=counts[3],
                           compliance_issues=counts[4],
                           activities=activities,
                           vehicle_types=vehicle_types,
                           driver_reporting=driver_reporting,
                           assignment_distribution=assignment_distribution,
                           active_assignments=active_assignments)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Log activity
            log_activity(user.id, 'Login', f"User {username} logged in")
            
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            password=generate_password_hash(password),
            role='user'
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        # Log activity
        log_activity(session['user_id'], 'Logout', f"User {session['username']} logged out")
        
        session.clear()
        flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login to access dashboard', 'warning')
        return redirect(url_for('login'))
    
    counts = get_dashboard_counts()
    
    # Get recent activities
    activities = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(10).all()
    
    return render_template('dashboard.html', 
                           vehicle_count=counts[0],
                           driver_count=counts[1],
                           assignment_count=counts[2],
                           maintenance_due=counts[3],
                           compliance_issues=counts[4],
                           activities=activities)

# VEHICLE MANAGEMENT
@app.route('/vehicles', methods=['GET', 'POST'])
def manage_vehicles():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        plate_number = request.form['plate_number'].upper().strip()
        
        # Check if plate number already exists
        if Vehicle.query.get(plate_number):
            flash('Plate number already exists!', 'danger')
            return redirect(url_for('manage_vehicles'))
        
        new_vehicle = Vehicle(
            plate_number=plate_number,
            chasis=request.form['chasis'],
            vehicle_type=request.form['vehicle_type'],
            make=request.form['make'],
            model=request.form['model'],
            year=request.form['year'],
            fuel_type=request.form['fuel_type'],
            fuel_capacity=float(request.form['fuel_capacity'] or 0),
            fuel_consumption=float(request.form['fuel_consumption'] or 0),
            loading_capacity=request.form['loading_capacity'],
            assigned_for=request.form['assigned_for']
        )
        db.session.add(new_vehicle)
        db.session.commit()
        
        # Log activity
        log_activity(session['user_id'], 'Add Vehicle', f"Added vehicle {plate_number}")
        
        flash('Vehicle added successfully!', 'success')
        return redirect(url_for('manage_vehicles'))
    
    vehicles = Vehicle.query.all()
    return render_template('vehicles.html', vehicles=vehicles)

@app.route('/vehicles/<plate_number>', methods=['GET', 'POST'])
def edit_vehicle(plate_number):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    vehicle = Vehicle.query.get_or_404(plate_number)
    
    if request.method == 'POST':
        vehicle.chasis = request.form['chasis']
        vehicle.vehicle_type = request.form['vehicle_type']
        vehicle.make = request.form['make']
        vehicle.model = request.form['model']
        vehicle.year = request.form['year']
        vehicle.fuel_type = request.form['fuel_type']
        vehicle.fuel_capacity = float(request.form['fuel_capacity'] or 0)
        vehicle.fuel_consumption = float(request.form['fuel_consumption'] or 0)
        vehicle.loading_capacity = request.form['loading_capacity']
        vehicle.assigned_for = request.form['assigned_for']
        db.session.commit()
        
        # Log activity
        log_activity(session['user_id'], 'Update Vehicle', f"Updated vehicle {plate_number}")
        
        flash('Vehicle updated successfully!', 'success')
        return redirect(url_for('manage_vehicles'))
    
    return render_template('edit_vehicle.html', vehicle=vehicle)

@app.route('/vehicles/delete/<plate_number>')
def delete_vehicle(plate_number):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    vehicle = Vehicle.query.get_or_404(plate_number)
    db.session.delete(vehicle)
    db.session.commit()
    
    # Log activity
    log_activity(session['user_id'], 'Delete Vehicle', f"Deleted vehicle {plate_number}")
    
    flash('Vehicle deleted successfully!', 'success')
    return redirect(url_for('manage_vehicles'))

# COMPLIANCE MANAGEMENT
@app.route('/compliance/<plate_number>', methods=['GET', 'POST'])
def manage_compliance(plate_number):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    vehicle = Vehicle.query.get_or_404(plate_number)
    compliance = Compliance.query.filter_by(plate_number=plate_number).first()
    
    if request.method == 'POST':
        if compliance:
            # Update existing compliance
            compliance.insurance_type = request.form['insurance_type']
            compliance.insurance_date = datetime.strptime(request.form['insurance_date'], '%Y-%m-%d').date() if request.form['insurance_date'] else None
            compliance.yearly_inspection = request.form['yearly_inspection']
            compliance.inspection_date = datetime.strptime(request.form['inspection_date'], '%Y-%m-%d').date() if request.form['inspection_date'] else None
            compliance.safety_audit = request.form['safety_audit']
            compliance.utilization_history = request.form['utilization_history']
            compliance.accident_history = request.form['accident_history']
        else:
            # Create new compliance
            new_compliance = Compliance(
                plate_number=plate_number,
                insurance_type=request.form['insurance_type'],
                insurance_date=datetime.strptime(request.form['insurance_date'], '%Y-%m-%d').date() if request.form['insurance_date'] else None,
                yearly_inspection=request.form['yearly_inspection'],
                inspection_date=datetime.strptime(request.form['inspection_date'], '%Y-%m-%d').date() if request.form['inspection_date'] else None,
                safety_audit=request.form['safety_audit'],
                utilization_history=request.form['utilization_history'],
                accident_history=request.form['accident_history']
            )
            db.session.add(new_compliance)
        
        db.session.commit()
        log_activity(session['user_id'], 'Update Compliance', f"Updated compliance for {plate_number}")
        flash('Compliance information saved!', 'success')
        return redirect(url_for('manage_compliance', plate_number=plate_number))
    
    return render_template('compliance.html', vehicle=vehicle, compliance=compliance)

# MAINTENANCE MANAGEMENT
@app.route('/maintenance/<plate_number>', methods=['GET', 'POST'])
def manage_maintenance(plate_number):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    vehicle = Vehicle.query.get_or_404(plate_number)
    maintenance_records = Maintenance.query.filter_by(plate_number=plate_number).all()
    
    if request.method == 'POST':
        # Add new maintenance record
        new_maintenance = Maintenance(
            plate_number=plate_number,
            last_service_km=int(request.form['last_service_km'] or 0),
            last_service_date=datetime.strptime(request.form['last_service_date'], '%Y-%m-%d').date() if request.form['last_service_date'] else None,
            next_service_km=int(request.form['next_service_km'] or 0),
            next_service_date=datetime.strptime(request.form['next_service_date'], '%Y-%m-%d').date() if request.form['next_service_date'] else None,
            maintenance_center=request.form['maintenance_center'],
            details=request.form['details']
        )
        db.session.add(new_maintenance)
        db.session.commit()
        log_activity(session['user_id'], 'Add Maintenance', f"Added maintenance for {plate_number}")
        flash('Maintenance record added!', 'success')
        return redirect(url_for('manage_maintenance', plate_number=plate_number))
    
    return render_template('maintenance.html', vehicle=vehicle, maintenance_records=maintenance_records)

@app.route('/maintenance/delete/<int:maintenance_id>')
def delete_maintenance(maintenance_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    maintenance = Maintenance.query.get_or_404(maintenance_id)
    plate_number = maintenance.plate_number
    db.session.delete(maintenance)
    db.session.commit()
    log_activity(session['user_id'], 'Delete Maintenance', f"Deleted maintenance record {maintenance_id}")
    flash('Maintenance record deleted!', 'success')
    return redirect(url_for('manage_maintenance', plate_number=plate_number))

# DRIVER MANAGEMENT
@app.route('/drivers', methods=['GET', 'POST'])
def manage_drivers():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Validate phone number
        phone = request.form['phone'].strip()
        if not phone.startswith('+251'):
            flash('Phone must start with +251', 'danger')
            return redirect(url_for('manage_drivers'))
        
        new_driver = Driver(
            name=request.form['name'],
            id_number=request.form['id_number'],
            phone=phone,
            reporting_to=request.form['reporting_to']
        )
        db.session.add(new_driver)
        db.session.commit()
        
        # Log activity
        log_activity(session['user_id'], 'Add Driver', f"Added driver {new_driver.name}")
        
        flash('Driver added successfully!', 'success')
        return redirect(url_for('manage_drivers'))
    
    drivers = Driver.query.all()
    return render_template('drivers.html', drivers=drivers)

@app.route('/drivers/<int:driver_id>', methods=['GET', 'POST'])
def edit_driver(driver_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    driver = Driver.query.get_or_404(driver_id)
    
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        if not phone.startswith('+251'):
            flash('Phone must start with +251', 'danger')
            return redirect(url_for('edit_driver', driver_id=driver_id))
            
        driver.name = request.form['name']
        driver.id_number = request.form['id_number']
        driver.phone = phone
        driver.reporting_to = request.form['reporting_to']
        db.session.commit()
        
        # Log activity
        log_activity(session['user_id'], 'Update Driver', f"Updated driver {driver.name}")
        
        flash('Driver updated successfully!', 'success')
        return redirect(url_for('manage_drivers'))
    
    return render_template('edit_driver.html', driver=driver)

@app.route('/drivers/delete/<int:driver_id>')
def delete_driver(driver_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    driver = Driver.query.get_or_404(driver_id)
    db.session.delete(driver)
    db.session.commit()
    
    # Log activity
    log_activity(session['user_id'], 'Delete Driver', f"Deleted driver {driver.name}")
    
    flash('Driver deleted successfully!', 'success')
    return redirect(url_for('manage_drivers'))

# ASSIGNMENT MANAGEMENT WITH GPS CONVERSION
@app.route('/assignments', methods=['GET', 'POST'])
def manage_assignments():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        plate_number = request.form['plate_number'].upper().strip()
        driver_id = request.form['driver_id']
        work_place = request.form['work_place']
        
        # Convert city name to GPS
        gps_position = convert_city_to_gps(work_place)
        gps_str = f"{gps_position[0]},{gps_position[1]}"
        
        # Check if vehicle exists
        if not Vehicle.query.get(plate_number):
            flash('Vehicle with this plate number does not exist!', 'danger')
            return redirect(url_for('manage_assignments'))
        
        new_assignment = Assignment(
            plate_number=plate_number,
            driver_id=driver_id,
            work_place=work_place,
            start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date() if request.form['end_date'] else None,
            gps_position=gps_str,
            geofence_violations=int(request.form['geofence_violations'] or 0))
        db.session.add(new_assignment)
        db.session.commit()
        
        # Log activity
        log_activity(session['user_id'], 'Add Assignment', f"Assigned vehicle {plate_number} to driver {driver_id}")
        
        flash('Assignment created successfully!', 'success')
        return redirect(url_for('manage_assignments'))
    
    assignments = Assignment.query.all()
    vehicles = Vehicle.query.all()
    drivers = Driver.query.all()
    return render_template('assignments.html', 
                           assignments=assignments, 
                           vehicles=vehicles, 
                           drivers=drivers,
                           cities=ETHIOPIAN_CITIES_GPS.keys())

@app.route('/assignments/edit/<int:assignment_id>', methods=['GET', 'POST'])
def edit_assignment(assignment_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    vehicles = Vehicle.query.all()
    drivers = Driver.query.all()
    
    if request.method == 'POST':
        work_place = request.form['work_place']
        
        # Convert city name to GPS
        gps_position = convert_city_to_gps(work_place)
        gps_str = f"{gps_position[0]},{gps_position[1]}"
        
        assignment.plate_number = request.form['plate_number'].upper().strip()
        assignment.driver_id = request.form['driver_id']
        assignment.work_place = work_place
        assignment.start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        assignment.end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date() if request.form['end_date'] else None
        assignment.gps_position = gps_str
        assignment.geofence_violations = int(request.form['geofence_violations'] or 0)
        db.session.commit()
        
        log_activity(session['user_id'], 'Update Assignment', f"Updated assignment {assignment_id}")
        flash('Assignment updated successfully!', 'success')
        return redirect(url_for('manage_assignments'))
    
    return render_template('edit_assignment.html', 
                           assignment=assignment,
                           vehicles=vehicles,
                           drivers=drivers,
                           cities=ETHIOPIAN_CITIES_GPS.keys())

@app.route('/assignments/delete/<int:assignment_id>')
def delete_assignment(assignment_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Admin access required', 'danger')
        return redirect(url_for('login'))
    
    assignment = Assignment.query.get_or_404(assignment_id)
    db.session.delete(assignment)
    db.session.commit()
    
    log_activity(session['user_id'], 'Delete Assignment', f"Deleted assignment {assignment_id}")
    flash('Assignment deleted successfully!', 'success')
    return redirect(url_for('manage_assignments'))

@app.route('/get_gps/<city>')
def get_gps(city):
    gps = convert_city_to_gps(city)
    return jsonify({'lat': gps[0], 'lng': gps[1]})

# REPORTING SECTION
@app.route('/reports')
def reports():
    if 'user_id' not in session:
        flash('Please login to access reports', 'warning')
        return redirect(url_for('login'))
    
    # Get counts for reports
    vehicle_count = Vehicle.query.count()
    driver_count = Driver.query.count()
    assignment_count = Assignment.query.filter(Assignment.end_date == None).count()
    
    # Get assignment distribution
    assignment_distribution = db.session.query(
        Vehicle.assigned_for,
        func.count(Vehicle.assigned_for)
    ).group_by(Vehicle.assigned_for).all()
    
    # Get recent assignments
    recent_assignments = Assignment.query.order_by(Assignment.start_date.desc()).limit(5).all()
    
    return render_template('reports.html', 
                           vehicle_count=vehicle_count,
                           driver_count=driver_count,
                           assignment_count=assignment_count,
                           assignment_distribution=assignment_distribution,
                           recent_assignments=recent_assignments)

# Add these new routes for filtered views
@app.route('/vehicles/filter/<vehicle_type>')
def vehicles_filtered(vehicle_type):
    vehicles = Vehicle.query.filter_by(vehicle_type=vehicle_type).all()
    return render_template('vehicles.html', vehicles=vehicles, filter=vehicle_type)

@app.route('/drivers/filter/<reporting_to>')
def drivers_filtered(reporting_to):
    drivers = Driver.query.filter_by(reporting_to=reporting_to).all()
    return render_template('drivers.html', drivers=drivers, filter=reporting_to)

@app.route('/assignments/filter/<assignment_type>')
def assignments_filtered(assignment_type):
    assignments = Assignment.query.join(Vehicle).filter(Vehicle.assigned_for == assignment_type).all()
    return render_template('assignments.html', assignments=assignments, 
                           vehicles=Vehicle.query.all(), 
                           drivers=Driver.query.all(),
                           cities=ETHIOPIAN_CITIES_GPS.keys(),
                           filter=assignment_type)

@app.route('/api/tracking/<plate_number>')
def get_tracking_data(plate_number):
    assignment = Assignment.query.filter_by(plate_number=plate_number, end_date=None).first()
    
    if not assignment:
        return jsonify({'error': 'No active assignment'}), 404
    
    # In a real system, this would get live data from GPS device
    # For demo, we'll simulate some data
    lat, lng = map(float, assignment.gps_position.split(','))
    
    # Simulate slight position changes
    lat += (random.random() - 0.5) * 0.01
    lng += (random.random() - 0.5) * 0.01
    
    return jsonify({
        'plate_number': plate_number,
        'position': f"{lat},{lng}",
        'lat': lat,
        'lng': lng,
        'speed': random.uniform(0, 120),
        'heading': random.uniform(0, 360),
        'status': 'moving' if random.random() > 0.3 else 'stopped',
        'last_update': datetime.utcnow().isoformat(),
        'violations': assignment.geofence_violations
    })

@app.route('/vehicle/details/<plate_number>')
def vehicle_details(plate_number):
    vehicle = Vehicle.query.get_or_404(plate_number)
    compliance = Compliance.query.filter_by(plate_number=plate_number).first()
    maintenance = Maintenance.query.filter_by(plate_number=plate_number).all()
    assignments = Assignment.query.filter_by(plate_number=plate_number).all()
    
    return render_template('vehicle_details.html', 
                           vehicle=vehicle, 
                           compliance=compliance,
                           maintenance=maintenance,
                           assignments=assignments)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1000, debug=True)
