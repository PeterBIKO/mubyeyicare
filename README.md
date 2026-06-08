# Post-Cesarean Wound Care Follow-Up System (MubyeYiCare)

## Overview

MubyeYiCare is a comprehensive web-based system designed to manage post-cesarean patient wound care follow-ups. It enables healthcare providers (doctors and nurses) to efficiently track, assess, and manage the wound healing progress of post-cesarean patients through an intuitive web interface.

## Features

### Core Functionality

1. **Patient Management**
   - Register and manage post-cesarean patients
   - Store comprehensive patient information including surgery details
   - Track patient demographics, contact information, and incision types
   - Monitor patient status (active/discharged)

2. **Follow-up Scheduling**
   - Schedule follow-up appointments (in-person, telemedicine, phone)
   - Manage follow-up dates and locations
   - Track completion status
   - Record vital signs during follow-ups

3. **Wound Assessment**
   - Detailed wound status evaluation (excellent, good, fair, poor, infected)
   - Track wound characteristics:
     - Redness, swelling, discharge
     - Dehiscence and infection signs
     - Incision length and depth measurements
   - Pain level tracking (0-10 scale)
   - Healing progress assessment

4. **Clinical Monitoring**
   - Record vital signs (BP, heart rate, temperature, oxygen saturation)
   - Track active medications
   - Monitor treatment recommendations
   - Automated alert system for critical observations

5. **Analytics & Reporting**
   - Dashboard with key statistics
   - Wound healing analytics
   - Visual charts and reports
   - Patient follow-up status overview

6. **User Management**
   - Role-based access control (Admin, Doctor, Nurse, Patient)
   - User authentication and authorization
   - Profile management
   - User registration (admin only)

## Technology Stack

- **Backend**: Python 3.8+ with Flask
- **Database**: SQLAlchemy ORM (SQLite/PostgreSQL compatible)
- **Frontend**: Bootstrap 5, HTML5, JavaScript
- **Authentication**: Flask-Login with password hashing
- **Additional**: Flask-WTF for form handling, python-dotenv for configuration

## Project Structure

```
mubyeyicare/
├── app.py                 # Flask application factory
├── config.py             # Configuration settings
├── models.py             # Database models
├── run.py                # Application entry point
├── requirements.txt      # Python dependencies
├── routes/
│   ├── auth.py          # Authentication routes
│   ├── dashboard.py     # Dashboard routes
│   ├── patients.py      # Patient management routes
│   ├── follow_ups.py    # Follow-up routes
│   └── assessments.py   # Assessment routes
└── templates/
    ├── base.html        # Base template
    ├── auth/            # Authentication templates
    ├── dashboard/       # Dashboard templates
    ├── patients/        # Patient templates
    ├── follow_ups/      # Follow-up templates
    └── assessments/     # Assessment templates
```

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Setup Steps

1. **Clone or download the project**
   ```bash
   cd mubyeyicare
   ```

2. **Create a virtual environment** (Windows)
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   **On macOS/Linux:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**
   ```bash
   python run.py
   ```
   
   Or use the CLI command:
   ```bash
   flask init-db
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

   The application will be available at `http://localhost:5000`

## Usage

### Default Credentials

After initialization, use the default admin credentials:
- **Username**: admin
- **Password**: admin123

### User Workflows

#### Administrator
1. Log in with admin credentials
2. Register new users (doctors/nurses)
3. View all patients and follow-ups
4. Monitor system analytics

#### Doctor/Nurse
1. Log in with assigned credentials
2. Add new patients to the system
3. Schedule follow-up appointments
4. Record wound assessments
5. Monitor patient progress
6. Generate reports

### Key Operations

1. **Add a New Patient**
   - Navigate to Patients → Add New Patient
   - Fill in patient details and surgery information
   - Submit to register

2. **Schedule a Follow-up**
   - View patient details
   - Click "Schedule New" in Follow-ups section
   - Select date, time, type, and location
   - Save follow-up appointment

3. **Record Wound Assessment**
   - From patient details, click "New Assessment"
   - Evaluate wound status and characteristics
   - Record measurements and observations
   - Save assessment

4. **Complete a Follow-up**
   - View pending follow-up
   - Mark as complete
   - Record vital signs if applicable
   - Add clinical notes

5. **View Analytics**
   - Navigate to Analytics
   - Review wound healing statistics
   - Analyze patient outcomes

## Database Models

### User
- Stores healthcare provider information
- Supports multiple roles (Admin, Doctor, Nurse, Patient)
- Password encryption for security

### Patient
- Patient demographics and medical record number (MRN)
- Surgery details (date, type, surgeon, incision type)
- Primary doctor assignment
- Active/discharged status

### FollowUp
- Scheduled follow-up appointments
- Follow-up type and location
- Completion tracking
- Associated vital signs and assessments

### WoundAssessment
- Comprehensive wound evaluation
- Status classification
- Clinical measurements
- Treatment recommendations

### VitalSigns
- Vital signs recorded during follow-ups
- Blood pressure, heart rate, temperature
- Oxygen saturation and respiratory rate

### MedicationLog
- Active medications
- Dosage and frequency
- Indication and duration

### Alert
- Critical observation alerts
- Severity levels
- Resolution tracking

## Configuration

Edit `config.py` to modify:
- Database URI
- Secret key (change in production)
- Session settings
- Debug mode (development only)

### Environment Variables

Set these for production deployment:
```
FLASK_ENV=production
SECRET_KEY=your-secure-secret-key
DATABASE_URL=postgresql://user:password@localhost/dbname
```

## Security Notes

1. **Change default admin password** immediately after first login
2. **Use HTTPS** in production (set SESSION_COOKIE_SECURE=True)
3. **Set a strong SECRET_KEY** in production
4. **Use PostgreSQL** instead of SQLite for production
5. **Implement CSRF protection** (already included via Flask-WTF)
6. **Regular backups** of the database

## API Endpoints

### Authentication
- `GET/POST /auth/login` - User login
- `GET/POST /auth/register` - Register new user (admin only)
- `GET /auth/logout` - User logout
- `GET /auth/profile` - View user profile

### Dashboard
- `GET /dashboard/` - Main dashboard
- `GET /dashboard/provider` - Provider dashboard
- `GET /dashboard/analytics` - Analytics view

### Patients
- `GET /patients/` - List all patients
- `GET/POST /patients/create` - Create new patient
- `GET /patients/<id>` - View patient details
- `GET/POST /patients/<id>/edit` - Edit patient
- `POST /patients/<id>/discharge` - Discharge patient

### Follow-ups
- `GET /follow-ups/patient/<id>` - View patient follow-ups
- `GET/POST /follow-ups/create/<id>` - Schedule follow-up
- `GET /follow-ups/<id>` - View follow-up details
- `GET/POST /follow-ups/<id>/complete` - Complete follow-up

### Assessments
- `GET /assessments/patient/<id>` - View patient assessments
- `GET/POST /assessments/create/<id>` - Create assessment
- `GET /assessments/<id>` - View assessment
- `GET/POST /assessments/<id>/edit` - Edit assessment

## Extending the System

### Adding Custom Fields
1. Modify the model in `models.py`
2. Create a database migration (or drop and recreate)
3. Update corresponding forms and templates

### Adding New Routes
1. Create new blueprint in `routes/`
2. Register blueprint in `app.py`
3. Create corresponding templates

### Customizing Templates
- All templates use Bootstrap 5
- Modify `templates/base.html` for site-wide changes
- Individual templates in respective subdirectories

## Troubleshooting

### Database Issues
```bash
# Reset database (development only)
rm cesarean_care.db
python run.py
```

### Port Already in Use
```bash
# Run on different port
python run.py --port 5001
```

### Module Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## Future Enhancements

- Patient mobile app
- SMS/Email reminders for appointments
- Advanced analytics and machine learning
- Integration with hospital EHR systems
- Multi-language support
- Mobile-responsive improvements
- Video consultation support
- Prescription generation and management
- Insurance billing integration

## Support & Maintenance

For issues, improvements, or feature requests:
1. Document the issue clearly
2. Include reproduction steps
3. Provide system details (OS, Python version)
4. Contact the development team

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Credits

Developed for post-cesarean wound care management.
Created with Flask and modern web technologies.

---

**Last Updated**: June 2026
**Version**: 1.0.0
