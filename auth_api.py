#!/usr/bin/env python3
"""
auth_api.py

Flask auth service with admin-approved signups, JWT login,
and manual CORS headers (no flask-cors dependency),
all endpoints handle OPTIONS preflight and verify tokens inside handlers.
"""
import os
from datetime import datetime
from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token, get_jwt_identity, verify_jwt_in_request
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask setup
app = Flask(__name__)
# auth.db beside this script
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(base_dir, 'auth.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret')

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Models
class PendingSignup(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    first_name    = db.Column(db.String(80), nullable=False)
    last_name     = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    requested_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class User(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    first_name    = db.Column(db.String(80), nullable=False)
    last_name     = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False, nullable=False)

# Create tables
with app.app_context():
    db.create_all()

# CORS helper
def corsify(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Authorization,Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS,DELETE'
    return resp

# Admin check
def is_current_admin():
    # must call verify_jwt_in_request before using
    uid = get_jwt_identity()
    if not uid:
        return False
    user = User.query.get(uid)
    return bool(user and user.is_admin)

# Routes
@app.route('/api/auth/signup', methods=['POST','OPTIONS'])
def signup_request():
    if request.method == 'OPTIONS':
        return corsify(make_response()), 200
    data = request.get_json(force=True)
    # validate
    for f in ('username','email','first_name','last_name','password'):
        if not data.get(f) or not str(data[f]).strip():
            return corsify(jsonify(msg='All fields are required.')), 400
    uname = data['username'].strip()
    email = data['email'].strip().lower()
    first = data['first_name'].strip()
    last  = data['last_name'].strip()
    pw    = data['password']
    # uniqueness
    if PendingSignup.query.filter_by(username=uname).first() or User.query.filter_by(username=uname).first():
        return corsify(jsonify(msg='Username already taken.')), 400
    if PendingSignup.query.filter_by(email=email).first() or User.query.filter_by(email=email).first():
        return corsify(jsonify(msg='Email already registered.')), 400
    # queue
    ps = PendingSignup(username=uname, email=email,
                       first_name=first, last_name=last,
                       password_hash=generate_password_hash(pw))
    db.session.add(ps)
    db.session.commit()
    return corsify(jsonify(msg='Signup request queued; await admin approval.')), 202

@app.route('/api/auth/login', methods=['POST','OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return corsify(make_response()), 200
    data = request.get_json(force=True)
    uname = data.get('username','').strip()
    pw    = data.get('password','')
    if not uname or not pw:
        return corsify(jsonify(msg='Username and password required.')), 400
    user = User.query.filter_by(username=uname).first()
    if not user or not check_password_hash(user.password_hash, pw):
        return corsify(jsonify(msg='Invalid credentials.')), 401
    token = create_access_token(identity=user.id)
    return corsify(jsonify(access_token=token)), 200

@app.route('/api/auth/me', methods=['GET','OPTIONS'])
def me():
    if request.method == 'OPTIONS':
        return corsify(make_response()), 200
    # verify JWT
    try:
        verify_jwt_in_request()
    except Exception:
        return corsify(jsonify(msg='Missing or invalid token.')), 401
    user = User.query.get(get_jwt_identity())
    return corsify(jsonify(
        username   = user.username,
        first_name = user.first_name,
        last_name  = user.last_name,
        is_admin   = user.is_admin
    )), 200

@app.route('/api/auth/signup-requests', methods=['GET','OPTIONS'])
def list_signup_requests():
    if request.method == 'OPTIONS':
        return corsify(make_response()), 200
    try:
        verify_jwt_in_request()
    except Exception:
        return corsify(jsonify(msg='Missing or invalid token.')), 401
    if not is_current_admin():
        return corsify(jsonify(msg='Forbidden')), 403
    pending = PendingSignup.query.order_by(PendingSignup.requested_at).all()
    data = [{'username':p.username,'email':p.email,
             'first_name':p.first_name,'last_name':p.last_name,
             'requested_at':p.requested_at.isoformat()} for p in pending]
    return corsify(jsonify(pending=data)), 200

@app.route('/api/auth/signup-approve', methods=['POST','OPTIONS'])

def approve_signup():
    if request.method == 'OPTIONS':
        return corsify(make_response()), 200
    try:
        verify_jwt_in_request()
    except Exception:
        return corsify(jsonify(msg='Missing or invalid token.')), 401
    if not is_current_admin():
        return corsify(jsonify(msg='Forbidden')), 403
    data = request.get_json(force=True)
    uname = data.get('username','').strip()
    p = PendingSignup.query.filter_by(username=uname).first()
    if not p:
        return corsify(jsonify(msg='Request not found.')), 404
    # migrate
    u = User(username=p.username, email=p.email,
             first_name=p.first_name, last_name=p.last_name,
             password_hash=p.password_hash,
             is_admin=(User.query.filter_by(is_admin=True).count()==0))
    db.session.add(u)
    db.session.delete(p)
    db.session.commit()
    return corsify(jsonify(msg=f'Approved {uname}.' )), 200

@app.route('/api/auth/signup-reject', methods=['POST','OPTIONS'])
def reject_signup():
    if request.method == 'OPTIONS':
        return corsify(make_response()), 200
    try:
        verify_jwt_in_request()
    except Exception:
        return corsify(jsonify(msg='Missing or invalid token.')), 401
    if not is_current_admin():
        return corsify(jsonify(msg='Forbidden')), 403
    data = request.get_json(force=True)
    uname = data.get('username','').strip()
    p = PendingSignup.query.filter_by(username=uname).first()
    if not p:
        return corsify(jsonify(msg='Request not found.')), 404
    db.session.delete(p)
    db.session.commit()
    return corsify(jsonify(msg=f'Rejected {uname}.' )), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
