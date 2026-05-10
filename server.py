from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import time
import random

app = Flask(__name__)
CORS(app)

# Structure: {"WriterName": 1715123456.0}
active_writers = {}

# Structure: {"WriterName": "🦊"}
# This ensures once a name is picked, their animal stays the same.
writer_icons = {}

# The menagerie of writing companions
ANIMALS = ["😺", "🐶", "🦊", "🐼", "🐨", "🦁", "🐯", "🐸", "🐙", "🦄", "🐹", "🐝", "🦖", "🐧", "🦤"]


@app.route('/universe')
def universe():
    return render_template('cat.html')


@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    data = request.json
    writer_id = data.get("writer", "Anonymous")

    # Assign a random animal if this name is new to the session
    if writer_id not in writer_icons:
        writer_icons[writer_id] = random.choice(ANIMALS)
        print(f"✨ New writer joined: {writer_id} assigned {writer_icons[writer_id]}")

    # Record the time of the pulse
    active_writers[writer_id] = time.time()
    print(f"✨ Heartbeat from {writer_id}")
    return jsonify({"status": "received"})


@app.route('/get-pulses', methods=['GET'])
def get_pulses():
    now = time.time()

    # Filter for writers active in the last 5 minutes (300 seconds)
    # Returns a list of objects so the HTML knows which icon to draw
    writing_now = []
    for writer, last_time in active_writers.items():
        if (now - last_time) < 300:
            writing_now.append({
                "name": writer,
                "icon": writer_icons.get(writer, "🐾")
            })

    return jsonify({"active_writers": writing_now})


if __name__ == '__main__':
    # host='0.0.0.0' allows the Raspberry Pi to be visible on your network
    app.run(host='0.0.0.0', port=5000)
