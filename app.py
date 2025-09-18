from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from models import db, User, Doctor
from flask_sqlalchemy import SQLAlchemy
from flask_pymongo import PyMongo 
import os
from datetime import datetime
import traceback
import mongo  # Ensure mongo.py is in the same directory
# Assuming functions.py is in the same directory
# Make sure functions.py includes the STANDARD_DISCLAIMER or define it here
try:
    from functions import (STANDARD_DISCLAIMER, gemini_generic,
                           gemini_interactive, gemini_text, get_image_urls)
except ImportError:
    # Define fallback if functions.py is missing or doesn't have the constant
    STANDARD_DISCLAIMER = "I am an AI chatbot, not a substitute for professional medical advice... Always seek the advice of your physician..."
    # Define dummy functions to prevent NameErrors if functions.py is missing
    def gemini_text(data): return {"response": f"Error: func missing. Input: {data}", "Disclaimer": STANDARD_DISCLAIMER}
    def gemini_generic(data): return {"is_medical_related_prompt": "No", "Disclaimer": STANDARD_DISCLAIMER}
    def gemini_interactive(msg, hist): return {"response": "Error: func missing.", "Disclaimer": STANDARD_DISCLAIMER, "conversation_complete": True}
    def get_image_urls(term, num): return [f"https://via.placeholder.com/150?text=Error+Func+Missing+{i+1}" for i in range(num)]

# Initialize the Flask application
app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

app.secret_key = "supersecretkey"  # Use env variables in production

# Configure SQLite database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'data.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# MongoDB connection
app.config["MONGO_URI"] = "mongodb://localhost:27017/health_db"
mongo = PyMongo(app)

# Initialize DB with app
db.init_app(app)

# Define the main route for the homepage
@app.route('/')
def index():
    """Renders the main chatbot page."""
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering template: {e}")
        return "Error loading page.", 500

# Route for simple, single-turn text generation
@app.route("/gemini/<data>")
def gemini_prompt_route(data: str):
    """
    Handles single-turn text prompts using gemini_text.
    Note: Path parameters can be fragile with complex inputs containing '/'.
    Consider using query parameters (?data=...) or POST for more robustness.
    """
    if not data:
        return jsonify({"data": {"response": "No input data provided.", "Disclaimer": STANDARD_DISCLAIMER}}), 400
    try:
        result = gemini_text(data)
        # Basic validation
        if not isinstance(result, dict):
             raise TypeError("Invalid response type from gemini_text")
        return jsonify({"data": result})
    except Exception as e:
        print(f"Error in /gemini route: {e}\n{traceback.format_exc()}")
        return jsonify({"data": {"response": f"Sorry, an error occurred processing your request: {e}", "Disclaimer": STANDARD_DISCLAIMER}}), 500

# Route for single-turn classification and structured output
@app.route("/gemini_generic/<data>")
def gemini_generic_route(data: str):
    """
    Processes a prompt using the gemini_generic function for classification
    and basic structured response (single turn).
    """
    if not data:
        return jsonify({"data": {"is_medical_related_prompt": "No", "Disclaimer": STANDARD_DISCLAIMER, "error": "No input data"}}), 400
    try:
        # The base_prompt logic is handled *inside* the refined gemini_generic function
        result = gemini_generic(data)
        # Basic validation
        if not isinstance(result, dict) or "is_medical_related_prompt" not in result:
             raise TypeError("Invalid response type from gemini_generic")
        return jsonify({"data": result})
    except Exception as e:
        print(f"Error in /gemini_generic route: {e}\n{traceback.format_exc()}")
        # Return a valid structure matching the expected output schema on error
        return jsonify({"data": {
            "Symptoms": ".",
            "Remedies": "",
            "Precautions": "",
            "Guidelines": "",
            "is_medical_related_prompt": "No", # Default to No on error
            "medication": [],
            "Disclaimer": STANDARD_DISCLAIMER,
            "error": f"An error occurred: {e}"
        }}), 500

# Route for handling interactive, multi-turn conversations
@app.route("/gemini-interactive", methods=["POST"])
def gemini_interactive_route():
    """
    Processes interactive conversation steps using gemini_interactive.
    Expects POST data: {"message": "...", "conversation_history": [...]}.
    Returns enhanced response with conversation context and potential UI suggestions.
    """
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({"error": "Invalid request. JSON body with 'message' field is required."}), 400

        message = data.get('message', '').strip()
        # Ensure history is None or a list
        conversation_history = data.get('conversation_history', None)
        if conversation_history is not None and not isinstance(conversation_history, list):
             return jsonify({"error": "Invalid request. 'conversation_history' must be a list or null."}), 400

        # --- Request Logging ---
        print(f"\n=== INTERACTIVE REQUEST ===")
        print(f"Message: '{message}'")
        print(f"History length: {len(conversation_history) if conversation_history else 0}")

        # --- Handle Restart ---
        if message.lower() in ["restart", "start over", "reset", "new conversation"]:
            print("--- User requested restart ---")
            # Return a response that signals the frontend to clear history
            return jsonify({"data": {
                "response": "Okay, let's start a new conversation. How can I help with your health questions today?",
                "needs_follow_up": False,
                "follow_up_question": "",
                "is_medical_related": True, # Assume starting medical
                "is_medical_related_prompt": "Yes",
                "can_provide_structured_response": False,
                "conversation_complete": False, # Start of new convo isn't complete
                "Disclaimer": STANDARD_DISCLAIMER,
                "conversation_restarted": True # Flag for frontend
            }})

        # --- Call Core Logic Function ---
        response = gemini_interactive(message, conversation_history)

        # --- Response Logging & Basic Validation ---
        print(f"--- GEMINI INTERACTIVE RESPONSE (raw) ---")
        print(response) # Print the whole raw response for debugging

        if not isinstance(response, dict):
             print("Error: gemini_interactive did not return a dictionary.")
             raise ValueError("Invalid response format from conversation engine.")

        # --- API Layer Sanity Checks & Failsafes ---

        # Failsafe: Force completion after excessive exchanges (e.g., > 5 user turns)
        # Add 1 for the current message to compare against history length
        total_messages = (len(conversation_history) if conversation_history else 0) + 1
        # Check if it's already complete *before* forcing it
        if not response.get("conversation_complete", False) and total_messages >= 100: # e.g., 50 user + 50 model turns + current msg
            print(f"--- API Failsafe: Forcing conversation completion after {total_messages} total messages ---")
            response["conversation_complete"] = True
            response["needs_follow_up"] = False
            response["follow_up_question"] = ""
            # Assume we can provide a structured response if it was medical and forced complete
            if response.get("is_medical_related", True):
                response["can_provide_structured_response"] = True

        # Failsafe: Fix logical inconsistencies if function didn't catch them
        if response.get("conversation_complete") and response.get("needs_follow_up"):
            print("--- API Failsafe: Fixing inconsistency: conversation_complete=True but needs_follow_up=True ---")
            response["needs_follow_up"] = False
            response["follow_up_question"] = "" # Clear the question too

        # Ensure standard disclaimer is present (should be handled by core func, but check here too)
        response.setdefault("Disclaimer", STANDARD_DISCLAIMER)

        # --- Final Response Logging ---
        print(f"--- API RESPONSE (processed) ---")
        # Log key fields after potential modifications
        log_keys = ["response", "needs_follow_up", "follow_up_question", "is_medical_related", "is_medical_related_prompt", "can_provide_structured_response", "conversation_complete", "Symptoms", "Remedies", "Precautions", "Guidelines"]
        for key in log_keys:
             if key in response:
                 value = response[key]
                 print(f"{key}: '{str(value)[:100]}...'" if isinstance(value, str) and len(value) > 100 else f"{key}: {value}")
        print("==========================")

        # Return the processed response
        return jsonify({"data": response})

    except Exception as e:
        print(f"!!! Error in /gemini-interactive route: {str(e)} !!!")
        traceback_str = traceback.format_exc()
        print(f"Traceback:\n{traceback_str}")

        # Return a structured error response matching the expected 'data' field
        return jsonify({
            "data": {
                "response": f"I apologize, but an internal error occurred ({type(e).__name__}). Please try again or restart the conversation.",
                "needs_follow_up": False,
                "follow_up_question": "",
                "is_medical_related": True, # Assume medical context on error unless known otherwise
                "is_medical_related_prompt": "Yes",
                "can_provide_structured_response": False,
                "conversation_complete": True, # Mark complete to stop potential loops
                "Disclaimer": STANDARD_DISCLAIMER,
                "error": str(e) # Include error message for debugging on client if needed
            }
        }), 500

# Route for image search
@app.route("/gemini/image/<search_term>")
def search_images_route(search_term: str):
    """
    Searches for images using the provided search term.
    """
    if not search_term:
        return jsonify([]), 400 # Return empty list for bad request

    num_results = 3  # Default number of images
    try:
        image_urls = get_image_urls(search_term, num_results)
        # Ensure it returns a list
        if not isinstance(image_urls, list):
             print(f"Warning: get_image_urls did not return a list for '{search_term}'")
             image_urls = [] # Return empty list if response format is wrong
        return jsonify(image_urls)

    except Exception as e:
        print(f"Error in /gemini/image route: {str(e)}\n{traceback.format_exc()}")
        # Provide fallback placeholder URLs on error
        try:
            safe_term = search_term.replace(' ', '-')[:20] # Basic sanitization for URL
            fallback_urls = [
                f"https://via.placeholder.com/150/FF0000/FFFFFF?text=Error+1+{safe_term}",
                f"https://via.placeholder.com/150/FF0000/FFFFFF?text=Error+2+{safe_term}",
                f"https://via.placeholder.com/150/FF0000/FFFFFF?text=Error+3+{safe_term}"
            ][:num_results]
        except Exception: # Failsafe for the failsafe
             fallback_urls = ["https://via.placeholder.com/150/FF0000/FFFFFF?text=Error"] * num_results

        return jsonify(fallback_urls), 500

# Doctor Registration
@app.route('/register-doctor', methods=['GET', 'POST'])
def register_doctor():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        license_number = request.form['license_number']
        location = request.form['location']
        affiliation = request.form['affiliation']
        specialization = request.form['specialization']

        if Doctor.query.filter_by(email=email).first():
           msg = "Email already registered, Please Login ."
           return render_template('login.html', message=msg)

        doctor = Doctor(
            full_name=full_name,
            email=email,
            phone=phone,
            password=password,
            specialization=specialization,
            license_number=license_number,
            location=location,
            affiliation=affiliation,
            created_at=datetime.utcnow()
        )

        db.session.add(doctor)
        db.session.commit()

        session['user_id'] = doctor.id
        session['user_name'] = doctor.full_name
        session['user_type'] = 'doctor'
        flash("Doctor registered successfully!", "success")
        return redirect(url_for('dashboard_doctor'))

    return render_template('doctor_register.html')

# Doctor Dashboard
@app.route('/dashboard-doctor')
def dashboard_doctor():
    if 'user_id' not in session or session.get('user_type') != 'doctor':
        flash("Access denied. Please login as a doctor.", "error")
        return redirect(url_for('login'))

    doctor = Doctor.query.get(session['user_id'])
    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for('login'))

    return render_template('dashboard_doctor.html', doctor=doctor)

# User Registration
@app.route('/register-user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        landmark = request.form['landmark']
        location = request.form['location']
        password = request.form['password']
        age = request.form['age']
        gender = request.form['gender']
        condition = request.form['condition']
        medications = request.form['medications']
        allergies = request.form['allergies']

        if User.query.filter_by(email=email).first():
            msg = "Email already registered, Please Login ."
            return render_template('login.html',message=msg)

        user = User(
            full_name=full_name,
            email=email,
            phone=phone,
            landmark=landmark,
            location=location,
            password=password,
            age=age,
            gender=gender,
            condition=condition,
            medications=medications,
            allergies=allergies,
            created_at=datetime.utcnow()
        )

        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        session['user_name'] = user.full_name
        session['user_type'] = 'user'

        flash("User registered successfully!", "success")
        return redirect(url_for('dashboard_user'))

    return render_template('user_register.html')

@app.route('/dashboard-user')
def dashboard_user():
    if 'user_id' not in session or session.get('user_type') != 'user':
        flash("Unauthorized access. Please login.", "error")
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash("User not found!", "error")
        return redirect(url_for('login'))

    return render_template('dashboard_user.html', user=user)

# Login Route (for both doctor and user)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        doctor = Doctor.query.filter_by(email=email, password=password).first()
        user = User.query.filter_by(email=email, password=password).first()

        if doctor:
            session['user_id'] = doctor.id
            session['user_name'] = doctor.full_name
            session['user_type'] = 'doctor'
            flash('Doctor logged in successfully!', 'success')
            return redirect(url_for('dashboard_doctor'))

        elif user:
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            session['user_type'] = 'user'
            flash("User logged in successfully!", "success")
            return redirect(url_for('dashboard_user'))

        else:
            msq= "Invalid email or password. Please try again."
            return render_template('login.html', message=msq)
            

    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('index'))

# Run the Flask app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
