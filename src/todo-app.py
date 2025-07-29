"""
A simple to do list app
"""
import os
import time
import urllib.request
import requests
from flask import Flask, render_template

app = Flask(__name__)

file_name = "/usr/src/app/static/image.jpg"
start_time = 0
timeout = int(os.environ.get("TIMEOUT"))


def download_image():
    """
    Download file from the source
    """
    global start_time
    with urllib.request.urlopen(url="https://picsum.photos/1200") as response, open(file_name, 'wb') as out_file:
        out_file.write(response.read())
    start_time = time.time()


def download_new():
    """
    Check if refresh needed
    """
    return time.time() - start_time > timeout

@app.route("/")
def index():
    """
    Serve the webpage
    """
    response = requests.get(url="http://todo-app-backend-svc:5555/todos", timeout=3)
    try:
        task_list = response.json()
    except Exception as e:
        print("Failed to parse JSON from backend:", e)
        task_list = []

    if download_new():
        download_image()
    return render_template("index.html",task_list=task_list)


if __name__ == "__main__":
    port = os.environ.get("PORT")
    print(f"Server started on port: {port}")
    app.run(host="0.0.0.0", port=int(port), debug=False)
