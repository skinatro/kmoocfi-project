import os
import logging
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
from nats import connect

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

username = os.environ.get("MONGO_USERNAME")
password = os.environ.get("MONGO_PASSWORD")
host = os.environ.get("MONGO_HOST")
db_name = os.environ.get("MONGO_DB")

MONGO_URI = f"mongodb://{username}:{password}@{host}:27017/{db_name}?authSource=admin"
client = MongoClient(MONGO_URI)
db = client[db_name]
todos_collection = db["todos"]

nats_client = None
nats_loop = None
nats_thread = None
executor = ThreadPoolExecutor(max_workers=2)

def start_nats_background():
    """Start NATS in a background thread with its own event loop"""
    global nats_loop, nats_client, nats_thread
    
    def run_nats():
        global nats_loop, nats_client
        nats_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(nats_loop)
        
        async def init_and_run():
            global nats_client
            try:
                nats_url = os.environ.get("NATS_URL", "nats://nats-service:4222")
                logging.info("Connected to NATS server")
                # Keep the loop running
                while True:
                    await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"Failed to connect to NATS: {e}")
                nats_client = None
        
        try:
            nats_loop.run_until_complete(init_and_run())
        except Exception as e:
            logging.error(f"NATS loop error: {e}")
        finally:
            if nats_loop:
                nats_loop.close()
    
    nats_thread = threading.Thread(target=run_nats, daemon=True)
    nats_thread.start()
    
    # Give it time to connect
    import time
    time.sleep(2)

def publish_to_nats_sync(message):
    """Synchronous wrapper for NATS publishing using the background loop"""
    global nats_loop, nats_client
    
    if not nats_client or not nats_loop:
        logging.warning("NATS not connected, skipping message")
        return
    
    async def publish():
        try:
            await nats_client.publish("db-updates", message.encode())
            logging.info("Published to NATS: %s", message)
        except Exception as e:
            logging.error(f"Failed to publish to NATS: {e}")
    
    try:
        future = asyncio.run_coroutine_threadsafe(publish(), nats_loop)
        future.result(timeout=5) 
    except Exception as e:
        logging.error(f"Error in publish_to_nats_sync: {e}")

@app.route("/todos", methods=["GET", "POST"])
def todos():
    if request.method == "GET":
        todos = list(todos_collection.find({}, {"_id": 1, "task": 1, "done": 1}))
        for t in todos:
            t["_id"] = str(t["_id"])
        logging.info("GET /todos - %d tasks fetched", len(todos))
        return jsonify(todos)

    elif request.method == "POST":  
        if request.content_type == 'application/json':
            new_task = request.json.get("task", "") if request.json else ""
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
            
            broadcast_message = json.dumps({
                "action": "create",
                "id": str(result.inserted_id),
                "task": new_task,
                "done": False
            })
            publish_to_nats_sync(f"NEW TODO: {broadcast_message}")
            
            return jsonify({"success": True, "id": str(result.inserted_id), "task": new_task})
        except Exception as e:
            logging.error(f"Failed to insert task: {e}")
            return "Internal Server Error", 500
    
    return "Method not allowed", 405

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
        
        broadcast_message = json.dumps({
            "action": "update",
            "id": task_id,
            "done": done_status
        })
        publish_to_nats_sync(f"TODO UPDATED: {broadcast_message}")
        
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
        client.server_info()
        nats_status = "connected" if nats_client else "disconnected"
        return jsonify({"database": "OK", "nats": nats_status}), 200
    except Exception as e:
        logging.error(f"Health check failed: {e}")
        return "Database connection error", 500

if __name__ == "__main__":
    PORT = os.environ.get("PORT", 5555)
    logging.info("Starting ToDo backend on port %s", PORT)
    
    start_nats_background()
    
    try:
        app.run(host="0.0.0.0", port=int(PORT), debug=True)
    finally:
        if nats_client:
            pass  # Connection will be cleaned up by daemon thread
        executor.shutdown(wait=True)
