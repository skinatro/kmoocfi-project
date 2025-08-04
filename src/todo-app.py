import os
import time
import urllib.request
import requests
from flask import Flask, render_template, request, redirect, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-here")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://todo-app-backend-svc:5555")
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT", "300"))  # 5 minutes default
STATIC_DIR = "/usr/src/app/static"
IMAGE_FILE = f"{STATIC_DIR}/image.jpg"

# Global variables for image management
start_time = 0

def ensure_static_dir():
    """Ensure static directory exists"""
    os.makedirs(STATIC_DIR, exist_ok=True)

def download_image():
    """Download a random image from picsum"""
    global start_time
    ensure_static_dir()
    try:
        with urllib.request.urlopen(url="https://picsum.photos/1200", timeout=10) as response:
            with open(IMAGE_FILE, "wb") as out_file:
                out_file.write(response.read())
        start_time = time.time()
        print("New image downloaded successfully")
    except Exception as e:
        print(f"Failed to download image: {e}")

def should_download_new():
    """Check if we need to download a new image"""
    if not os.path.exists(IMAGE_FILE):
        return True
    return time.time() - start_time > TIMEOUT_SECONDS

@app.route("/")
def index():
    """Serve the main todo page"""
    try:
        # Fetch todos from backend
        response = requests.get(f"{BACKEND_URL}/todos", timeout=5)
        response.raise_for_status()
        all_tasks = response.json()
    except requests.RequestException as e:
        print(f"Failed to fetch tasks from backend: {e}")
        all_tasks = []
        flash("Unable to load tasks from server", "error")
    except ValueError as e:
        print(f"Failed to parse JSON from backend: {e}")
        all_tasks = []
        flash("Server returned invalid data", "error")

    # Separate pending and completed tasks
    task_list = [task for task in all_tasks if not task.get("done", False)]
    tasks_done = [task for task in all_tasks if task.get("done", False)]

    # Download new image if needed
    if should_download_new():
        download_image()

    return render_template("index.html", task_list=task_list, tasks_done=tasks_done)

@app.route("/todos", methods=["POST"])
def create_todo():
    """Create a new todo by proxying to backend"""
    todo_text = request.form.get("todo", "").strip()
    
    if not todo_text:
        flash("Task cannot be empty", "error")
        return redirect("/")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/todos",
            data={"todo": todo_text},
            timeout=5
        )
        
        if response.status_code == 200:
            flash("Task created successfully", "success")
        else:
            flash(f"Failed to create task: {response.text}", "error")
            
    except requests.RequestException as e:
        print(f"Error creating task: {e}")
        flash("Unable to create task - server error", "error")
    
    return redirect("/")

@app.route("/todo/<task_id>", methods=["POST"])
def mark_as_done(task_id):
    """Mark a todo as done """
    
    try:
        response = requests.put(
            f"{BACKEND_URL}/todos/{task_id}",
            json={"done": True},  # Always mark as done
            timeout=5,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            flash("Task completed successfully", "success")
        elif response.status_code == 404:
            flash("Task not found", "error")
        else:
            flash(f"Failed to complete task: {response.text}", "error")
            
    except requests.RequestException as e:
        print(f"Error marking task {task_id} as done: {e}")
        flash("Unable to complete task - server error", "error")
    
    return redirect("/")



@app.route("/healthz", methods=["GET"])
def healthz():
    """Health check endpoint for frontend"""
    try:
        # Check if backend is reachable
        response = requests.get(f"{BACKEND_URL}/healthz", timeout=3)
        if response.status_code == 200:
            return "OK", 200
        else:
            print(f"Backend health check failed with status: {response.status_code}")
            return "Backend unhealthy", 503
    except requests.RequestException as e:
        print(f"Backend health check failed: {e}")
        return "Backend unreachable", 503

if __name__ == "__main__":
    PORT = os.environ.get("PORT", 5000)
    print(f"Frontend server starting on port: {PORT}")
    print(f"Backend URL: {BACKEND_URL}")
    
    # Download initial image
    download_image()
    
    app.run(host="0.0.0.0", port=int(PORT), debug=False)
