import subprocess
import sys
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("menu.html")


@app.route("/launch", methods=["POST"])
def launch():
    username = request.form.get("username", "").strip()
    role     = request.form.get("role", "LEFT").strip().upper()

    if not username:
        return jsonify({"error": "Pseudo requis"}), 400

    python = sys.executable
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

    subprocess.Popen(
        [python, script, "--username", username, "--role", role],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    return jsonify({"status": "launched"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
