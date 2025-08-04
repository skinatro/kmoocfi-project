import os
import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# MongoDB configuration
username = os.environ.get("MONGO_USERNAME")
password = os.environ.get("MONGO_PASSWORD")
host = os.environ.get("MONGO_HOST")
db_name = os.environ.get("MONGO_DB")

MONGO_URI = f"mongodb://{username}:{password}@{host}:27017/{db_name}?authSource=admin"
client = MongoClient(MONGO_URI)
db = client[db_name]
todos_collection = db["todos"]

@app.route("/todos", methods=["GET", "POST"])
def todos():
    if request.method == "GET":
        todos = list(todos_collection.find({}, {"_id": 1, "task": 1, "done": 1}))
        for t in todos:
            t["_id"] = str(t["_id"])
        logging.info("GET /todos - %d tasks fetched", len(todos))
        return jsonify(todos)

    if request.method == "POST":
        # Handle both form data and JSON
        if request.content_type == 'application/json':
            new_task = request.json.get("task", "")
        else:
            new_task = request.form.get("todo", "")
            
        logging.info("POST /todos - Received: %r", new_task)

        if not new_task:
            logging.warning("POST /todos - Empty task received")
            return "Empty task not allowed", 400

        if len(new_task) > 140:
            logging.warning("POST /todos - Task exceeds 140 characters: %r", new_task)
            return "Task too long (max 140 characters)", 400

        try:
            result = todos_collection.insert_one({"task": new_task, "done": False})
            logging.info("POST /todos - Task added: %r", new_task)
            return jsonify({"success": True, "id": str(result.inserted_id), "task": new_task})
        except Exception as e:
            logging.error(f"Failed to insert task: {e}")
            return "Internal Server Error", 500

@app.route("/todos/<task_id>", methods=["PUT"])
def update_todo(task_id):
    try:
        if not ObjectId.is_valid(task_id):
            logging.warning("PUT /todos/%s - Invalid ObjectId", task_id)
            return "Invalid task ID", 400

        data = request.get_json()
        if not data or "done" not in data:
            logging.warning("PUT /todos/%s - Missing 'done' field", task_id)
            return "Missing 'done' field in request body", 400

        done_status = bool(data["done"])

        result = todos_collection.update_one(
            {"_id": ObjectId(task_id)}, {"$set": {"done": done_status}}
        )

        if result.matched_count == 0:
            logging.warning("PUT /todos/%s - Task not found", task_id)
            return "Task not found", 404

        logging.info("PUT /todos/%s - Done status updated to: %s", task_id, done_status)
        return jsonify({"success": True, "id": task_id, "done": done_status})

    except Exception as e:
        logging.error(f"Failed to update task {task_id}: {e}")
        return "Internal Server Error", 500

@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Todo Backend API is running", "version": "1.0"}), 200

@app.route("/healthz", methods=["GET"])
def healthz():
    """Health check endpoint for Kubernetes probes."""
    try:
        # Test MongoDB connection
        client.server_info()
        return "OK", 200
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return "Database connection error", 500

if __name__ == "__main__":
    PORT = os.environ.get("PORT", 5555)
    logging.info("Starting ToDo backend on port %s", PORT)
    app.run(host="0.0.0.0", port=int(PORT), debug=False)
