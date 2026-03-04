import os, time, base64, io, logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from PIL import Image
import google.genai as genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wasel-gcp")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY environment variable is not set. API calls will fail.")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODEL = "gemini-2.0-flash"

PROMPT = """You are a sign language interpreter.
If you see a hand gesture or sign: reply ONLY the meaning (1-3 words in Arabic).
If no gesture: reply ...
No explanations. Just the word."""

app = Flask(__name__)
CORS(app)

# Extreme speed: limit payload size to ~20KB max
MAX_PAYLOAD_SIZE = 25_000

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    start_time = time.time()
    
    if not client:
        return jsonify({'translation': 'API Key Missing'}), 500
        
    try:
        data = request.json
        b64_string = data.get('image', '')
        
        if not b64_string:
            return jsonify({'translation': '...'}), 400

        # Enforce max payload for extreme speed
        if len(b64_string) > MAX_PAYLOAD_SIZE:
             logger.warning(f"Payload size {len(b64_string)} exceeds limit. Truncating or rejecting.")
             return jsonify({'translation': '...'}), 400

        img_b = base64.b64decode(b64_string.split(',')[1])
        pil_img = Image.open(io.BytesIO(img_b)).convert('RGB')
        
        # We don't thumbnail here because the frontend already scales down to 320x240
        # and compresses to WebP 0.3, ensuring maximum speed.
        
        response = client.models.generate_content(
            model=MODEL,
            contents=[PROMPT, pil_img],
            config=types.GenerateContentConfig(
                max_output_tokens=20, 
                temperature=0.1
            )
        )
        
        result = response.text.strip()
        ms = int((time.time() - start_time) * 1000)
        
        if result == "...":
            return "", 204 # No gesture, save bandwidth

        return jsonify({
            'translation': result,
            'processing_time_ms': ms
        }), 200

    except Exception as e:
        logger.error(f"API Error: {e}")
        return jsonify({'translation': '...'}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
