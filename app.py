import os, base64, io
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from PIL import Image
import google.genai as genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODEL = "gemini-2.0-flash"

PROMPT = """أنت مترجم لغة إشارة مصري خبير لخدمة عملاء "مصر الرقمية".
قواعد صارمة جداً للسرعة الفائقة:
1. انظر فوراً لحركة اليد والأصابع.
2. إذا وجدت أي إشارة (مثل: بطاقة، استعلام، مرور، تجديد، توثيق، دفع، أو إشارات الترحيب): أعد كلمة واحدة أو كلمتين فقط بالعربية.
3. إذا كان الشخص ثابتاً ولا يحرك يده: أعد فقط ...
4. ممنوع كتابة أي شرح. الكلمة فقط."""

app = Flask(__name__)
# Enable CORS and optimize Flask config
CORS(app)
app.config['JSON_AS_ASCII'] = False

PAGE = r"""
<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Wasel v4 Pro - HyperFast</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;font-family:'Segoe UI',sans-serif;overflow:hidden;height:100vh}
#c{position:relative;width:100vw;height:100vh}
video{width:100%;height:100%;object-fit:cover;transform:scaleX(-1)}
#top{position:absolute;top:0;left:0;right:0;padding:18px 28px;
background:linear-gradient(180deg,rgba(0,0,0,0.85) 0%,transparent 100%);z-index:9}
#brand{color:#666;font-size:13px;letter-spacing:3px;text-transform:uppercase}
#txt{color:#00ff88;font-size:52px;font-weight:700;margin-top:6px;
text-shadow:0 2px 20px rgba(0,255,136,0.5);min-height:75px;transition:color .1s ease}
#startBtn{margin-top:10px;padding:10px 24px;font-size:16px;font-weight:bold;
background:#00ff88;color:#000;border:none;border-radius:30px;cursor:pointer;}
#bot{position:absolute;bottom:16px;right:24px;color:#fff;font-size:13px;
background:rgba(0,0,0,0.7);padding:6px 12px;border-radius:6px;z-index:9;font-family:monospace}
</style></head><body>
<div id='c'>
<video id='v' autoplay playsinline muted></video>
<div id='top'><div id='brand'>WASEL v4 PRO — HYPERFAST ENGINE</div>
<div id='txt'>Starting camera...</div>
<button id="startBtn" onclick="toggle()" style="display:none;">⚡ تشغيل الترجمة الفورية</button>
</div>
<div id='bot'>Processing Engine</div>
</div>
<!-- Hardware Accelerated Canvas -->
<canvas id='cv' style='display:none'></canvas>
<script>
const v=document.getElementById('v'), cv=document.getElementById('cv'),
// willReadFrequently optimizes memory reading for constant polling
cx=cv.getContext('2d', { willReadFrequently: true, alpha: false }),
tx=document.getElementById('txt'), bt=document.getElementById('bot'), 
btn=document.getElementById('startBtn');

let running=false;
let frameCount=0;

// Request optimal camera config
navigator.mediaDevices.getUserMedia({video:{width:640,height:480,facingMode:'user',frameRate:30}})
.then(s=>{
    v.srcObject=s;
    tx.textContent='الكاميرا جاهزة';
    tx.style.color='#777';
    btn.style.display="inline-block";
}).catch(e=>{tx.textContent='Camera: '+e.message});

function toggle() {
    if(!running) {
        running=true;
        btn.textContent="⏹ إيقاف";
        btn.style.background="#ff4444"; btn.style.color="#fff";
        tx.textContent='أشر بيدك...'; tx.style.color='#555';
        fastLoop(); // Start aggressive loop
    } else {
        location.reload(); // Hard stop for immediate release
    }
}

async function fastLoop(){
    if(!running) return;
    
    // Hyper compression: 512x384 WebP @ 0.2 quality (approx 4-6KB)
    cv.width = 512; cv.height = 384; 
    cx.save(); cx.scale(-1,1); cx.drawImage(v, -512, 0, 512, 384); cx.restore();
    const payload = cv.toDataURL('image/webp', 0.2); 
    
    const startMs = Date.now();
    bt.textContent='⚡ Uploading ['+Math.round(payload.length/1024)+'KB]...';
    
    try {
        // Send directly as plain text for ZERO latency JSON parsing overhead on browser side
        const res = await fetch('/t', {
            method: 'POST', 
            headers: {'Content-Type': 'text/plain'}, 
            body: payload
        });
        
        const text = await res.text();
        const rtt = Date.now() - startMs;
        
        if (text === '...' || text.length < 2) {
            tx.textContent = 'أشر بيدك...';
            tx.style.color = '#555';
        } else if (text.startsWith('Err')) {
            tx.textContent = text;
            tx.style.color = '#ff4444';
        } else {
            tx.textContent = text;
            tx.style.color = '#00ff88'; // Flash bright green on success
        }
        
        frameCount++;
        bt.textContent=`🚀 Gemini 2.0 | RTT: ${rtt}ms | F: ${frameCount}`;
        
    } catch(e) {
        bt.textContent='Err: '+e.message;
    }
    
    // Recursive loop with aggressive 100ms throttle to prevent UI thread freezing
    setTimeout(fastLoop, 100); 
}
</script></body></html>
"""

@app.route('/')
def index():
    return render_template_string(PAGE)

# Minimal endpoint taking absolute shortest path
@app.route('/t', methods=['POST'])
def fast_translate():
    if not client:
        return 'Err: API KEY MISSING', 500
    try:
        # Expected plain text body: data:image/webp;base64,....
        b64_data = request.data.decode('utf-8')
        if ',' not in b64_data: return '...', 200
        
        # Immediate decode
        img_bytes = base64.b64decode(b64_data.split(',')[1])
        
        # Directly pass bytes to Gemini (saves PIL processing ms if API supports it, 
        # but PIL is safer for formatting. We'll use PIL for reliability, it takes <2ms)
        pil = Image.open(io.BytesIO(img_bytes))
        
        r = client.models.generate_content(
            model=MODEL, 
            contents=[PROMPT, pil],
            config=types.GenerateContentConfig(
                max_output_tokens=10, # Cut off early for speed
                temperature=0.0       # Deterministic, max speed
            )
        )
        return r.text.strip(), 200
    except Exception as e:
        return f'Err: {str(e)[:40]}', 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Threaded mode for maximum concurrency
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
