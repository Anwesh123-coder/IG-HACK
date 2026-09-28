from flask import Flask, request, jsonify
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'captured_screens'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/upload', methods=['POST'])
def upload_screen():
    if 'screenshot' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['screenshot']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save file with a unique timestamp or ID
    save_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(save_path)
    
    print(f"[!] Received screenshot: {save_path}")
    return jsonify({"status": "success", "message": "Screenshot captured"}), 200

if __name__ == '__main__':
    # Run on all interfaces (0.0.0.0) on port 5000
    app.run(host='0.0.0.0', port=5000)
