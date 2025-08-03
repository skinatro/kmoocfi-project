import os
import logging
from flask import Flask, request, jsonify, redirect
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# MongoDB connection
username = os.environ.get("MONGO_USERNAME")
password = os.environ.get("MONGO_PASSWORD")
host = os.environ.get("MONGO_HOST")
db_name = os.environ.get("MONGO_DB")

MONGO_URI = f"mongodb://{username}:{password}@{host}:27017/{db_name}?authSource=admin"
client = MongoClient(MONGO_URI)
db = client[db_name]
todos_collection = db["todos"]


@app.route('/todos', methods=['GET', 'POST'])
def todos():
    if request.method == 'GET':
        todos = list(todos_collection.find({}, {"_id": 1, "task": 1}))
        for t in todos:
            t["_id"] = str(t["_id"])
        logging.info("GET /todos - %d tasks fetched", len(todos))
        return jsonify(todos)

    if request.method == 'POST':
        new_task = request.form.get('todo', '')
        logging.info("POST /todos - Received: %r", new_task)

        if not new_task:
            logging.warning("POST /todos - Empty task received")
            return "Empty task not allowed", 400

        if len(new_task) > 140:
            logging.warning("POST /todos - Task exceeds 140 characters: %r", new_task)
            return "Task too long (max 140 characters)", 400

        try:
            todos_collection.insert_one({"task": new_task})
        except Exception as e:
            logging.error(f"Failed to insert task: {e}")
            return "Internal Server Error", 500

        logging.info("POST /todos - Task added: %r", new_task)
        return redirect("/")

@app.route("/", methods=["GET"])
def index():
    return "Backend is running", 200
@app.route('/healthz', methods=['GET'])
def healthz():
    """
    Health check endpoint for Kubernetes probes.
    Checks MongoDB connectivity.
    """
    try:
        # 'server_info()' is cheap and a good connectivity check
        _ = client.server_info()
        return "OK", 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return "Database connection error", 500


if __name__ == '__main__':
    PORT = os.environ.get("PORT")
    logging.info("Starting ToDo backend on port %s", PORT)
    app.run(host="0.0.0.0", port=int(PORT), debug=False)
