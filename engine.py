import numpy as np
import logging
from scipy.spatial.distance import euclidean
from fastdtw import fastdtw
import google.genai as genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wasel-engine")

class WaselEngine:
    """
    Tier 2 Gateway & Semantic Router (Fast-Path Pattern)
    Combines rapid deterministic math (DTW) with fallback Generative AI (Gemini).
    """
    def __init__(self, gemini_api_key=None, dtw_threshold=50.0):
        self.threshold = dtw_threshold
        self.client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None
        self.MODEL = "gemini-2.0-flash"
        
        # ---------------------------------------------------------
        # 🧠 الخطوة 1: قاعدة المعرفة المصغرة (Gesture Knowledge Base)
        # ---------------------------------------------------------
        # هنا يتم تخزين البصمات الرياضية (Vector Signatures) للجمل الخمس.
        # حالياً نضع بيانات وهمية، لاحقاً ستقوم بتسجيل حركات حقيقية وحفظها في ملف JSON.
        # الإحداثيات تكون مثلاً: 15 إطار * 21 نقطة لليد * 3 أبعاد (x, y, z) = 63 ميزة لكل إطار.
        self.knowledge_base = {
            "أريد تجديد البطاقة": self._load_signature_from_db("renew_id", frames=15),
            "أين شباك الخزينة؟": self._load_signature_from_db("cashier", frames=18),
            "دفع فاتورة": self._load_signature_from_db("pay_bill", frames=12),
            "استعلام عن مخالفات المرور": self._load_signature_from_db("traffic_fines", frames=20),
            "شكراً لك": self._load_signature_from_db("thank_you", frames=10)
        }

    def _load_signature_from_db(self, name, frames=15):
        """
        دالة مساعدة: في المستقبل ستستدعي الإحداثيات الحقيقية المُسجلة مسبقاً من قاعدة البيانات.
        حالياً تُولد بصمة عشوائية لغرض الهيكلة (Scaffolding).
        """
        return np.random.rand(frames, 63) # 63 features = 21 landmarks * 3 (x,y,z)

    # ---------------------------------------------------------
    # ⚡ الخطوة 2: المطابقة المتوازية (Parallel Vector Matching)
    # ---------------------------------------------------------
    def match_gesture_signature(self, incoming_sequence):
        """
        المرور السريع (Fast-Path): يستخدم Dynamic Time Warping (DTW) 
        لمقارنة الحركة الحالية بالبصمات المحفوظة. أسرع وأدق من أي LLM.
        """
        if not incoming_sequence or len(incoming_sequence) < 5:
            return False, None, float('inf')
            
        incoming_seq_np = np.array(incoming_sequence)
        best_match = None
        best_score = float('inf')
        
        # مقارنة الحركة مع كل البصمات المحفوظة
        for text, stored_sig in self.knowledge_base.items():
            # خوارزمية DTW تعالج اختلاف سرعة الإشارة بين شخص وآخر بعبقرية
            distance, _ = fastdtw(incoming_seq_np, stored_sig, dist=euclidean)
            
            if distance < best_score:
                best_score = distance
                best_match = text
                
        # إذا كانت المسافة أقل من العتبة المسموحة، إذاً التطابق شبه تام (Hit > 90%)
        if best_score < self.threshold:
            logger.info(f"⚡ FAST-PATH HIT: {best_match} (Score: {best_score:.2f})")
            return True, best_match, best_score
            
        logger.info(f"🐌 FAST-PATH MISS (Best Score: {best_score:.2f})")
        return False, None, best_score

    # ---------------------------------------------------------
    # 🛤️ الخطوة 3: اتخاذ القرار (Routing)
    # ---------------------------------------------------------
    def analyze_frames(self, incoming_sequence, raw_images=None):
        """
        المتحكم الرئيسي: يقرر أين تذهب البيانات (المسار السريع أم مسار الذكاء الاصطناعي).
        
        المتغيرات:
        - incoming_sequence: مصفوفة الإحداثيات المستخرجة بواسطة MediaPipe في الـ Frontend.
        - raw_images: الصور الخام (اختياري) التي تُرسل لـ Gemini في حال فشل المسار السريع.
        """
        import time
        start_time = time.time()
        
        # 1. محاولة المسار السريع أولاً (Tier 2 Semantic Cache)
        is_hit, fast_text, score = self.match_gesture_signature(incoming_sequence)
        dtw_time = (time.time() - start_time) * 1000
        
        if is_hit:
            return {
                "translation": fast_text,
                "source": "fast-path-dtw",
                "score": round(score, 2),
                "latency_ms": round(dtw_time, 2)
            }
            
        # 2. المسار المعقد (Tier 3 Gemini LLM Fallback)
        if not self.client or not raw_images:
            return {
                "translation": "...",
                "source": "fallback-failed",
                "latency_ms": round(dtw_time, 2)
            }
            
        try:
            start_llm = time.time()
            prompt = """أنت مترجم لغة إشارة مصري خبير لخدمة عملاء "مصر الرقمية". ترجم الإشارة إلى جملة دقيقة ومختصرة."""
            
            # Send images to Gemini
            r = self.client.models.generate_content(
                model=self.MODEL, 
                contents=[prompt] + raw_images, # raw_images is a list of PIL Images
                config=types.GenerateContentConfig(max_output_tokens=15, temperature=0.0)
            )
            
            llm_time = (time.time() - start_llm) * 1000
            total_time = (time.time() - start_time) * 1000
            
            return {
                "translation": r.text.strip(),
                "source": "gemini-llm",
                "latency_ms": round(total_time, 2),
                "llm_time_ms": round(llm_time, 2)
            }
        except Exception as e:
            return {
                "translation": f"Err: {str(e)[:40]}",
                "source": "error",
                "latency_ms": 0
            }

if __name__ == "__main__":
    # Test block to verify architecture behavior
    engine = WaselEngine()
    print("Testing Semantic Cache Routing...")
    
    # Simulate a perfect match sequence
    test_coords = engine.knowledge_base["شكراً لك"].tolist()
    result = engine.analyze_frames(test_coords)
    print(f"Test Result: {result}")
