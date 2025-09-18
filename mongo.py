# # Store query with email from session
# from flask import Flask, app, session, request, jsonify
# import mongo

# app=Flask(__name__)

# @app.route("/submit_query", methods=["POST"])
# def submit_query():
#     if "email" not in session:
#         return jsonify({"message": "User not logged in"}), 401

#     data = request.get_json()
#     query = data.get("query")
#     email = session["email"]

#     if not query:
#         return jsonify({"message": "Query required"}), 400

#     # Store in MongoDB
#     mongo.db.queries.insert_one({
#         "email": email,
#         "query": query
#     })

#     return jsonify({"message": f"Query saved for {email}!"})