# models.py
from flask_sqlalchemy import SQLAlchemy # pyright: ignore[reportMissingImports]
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):

    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    landmark = db.Column(db.String(150))
    location = db.Column(db.String(100))
    condition = db.Column(db.Text)
    medications = db.Column(db.Text)
    allergies = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.name,self.email}>'


# for doctors register^n

class Doctor(db.Model):

    __tablename__ = 'doctor'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=False, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(20))
    specialization = db.Column(db.String(100))
    license_number = db.Column(db.String(50), unique=False)
    location = db.Column(db.String(100))
    affiliation = db.Column(db.String(150))
    # certificate_filename = db.Column(db.String(200))
    # availability_status = db.Column(db.String(50), default='Offline')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Doctor {self.name ,self.email}>'