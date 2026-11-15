from flask import Flask, render_template, request
import subprocess
import os
import sys

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start')
def start_game():
    level = request.args.get('level', '1')
    # Ejecutar en una nueva ventana (solo en Windows)
    subprocess.Popen(["python", "main.py", level], creationflags=subprocess.CREATE_NEW_CONSOLE)
    return ('', 204)

if __name__ == '__main__':
    app.run(debug=True)
