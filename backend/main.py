from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
import requests
import json
import os

# -------------------------
# Setup
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI()

# Serve frontend
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend"), name="static")

@app.get("/")
def serve_ui():
    return FileResponse(BASE_DIR / "frontend" / "index.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Models
# -------------------------
class MarketingInput(BaseModel):
    company: str
    campaign: str
    description: str

# -------------------------
# Gemini Config
# -------------------------
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# -------------------------
# API
# -------------------------
@app.post("/generate")
async def generate_marketing_content(data: MarketingInput):

    prompt = (
        "You are a marketing expert. Return ONLY valid JSON (no markdown). "
        'Keys: "email", "whatsapp", "linkedin".\n\n'
        f"Company: {data.company}\n"
        f"Campaign: {data.campaign}\n"
        f"Description: {data.description}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(GEMINI_URL, json=payload)
        result = response.json()

        # 🔥 Debug (optional)
        print("Gemini Response:", result)

        if "candidates" not in result:
            return {"error": result.get("error", "Invalid API response")}

        text_output = result["candidates"][0]["content"]["parts"][0]["text"]

        clean_text = text_output.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(clean_text)
        except:
            # fallback if JSON parsing fails
            return {
                "email": text_output,
                "whatsapp": text_output,
                "linkedin": text_output
            }

    except Exception as e:
        return {"error": str(e)}

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)






# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# import os
# from fastapi import FastAPI
# from pydantic import BaseModel
# from dotenv import load_dotenv
# import requests
# import json
# from fastapi.middleware.cors import CORSMiddleware

# from pathlib import Path

# BASE_DIR = Path(__file__).resolve().parent.parent

# # Load environment variables
# load_dotenv()
# API_KEY = os.getenv("GEMINI_API_KEY")

# app = FastAPI()
# # app.mount("/static", StaticFiles(directory="frontend"), name="static")
# app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend"), name="static")
# @app.get("/")
# def serve_ui():
#     return FileResponse(BASE_DIR / "frontend" / "index.html")

# # @app.get("/")
# # def read_root():
# #     return {"message": "Marketing AI Tool API is running"}



# # IMPORTANT: This allows your HTML file to talk to your Python backend
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Gemini API Endpoint
# GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# class MarketingInput(BaseModel):
#     company: str
#     campaign: str
#     description: str

# @app.post("/generate")
# async def generate_marketing_content(data: MarketingInput):
#     # This prompt tells Gemini exactly how to format the data
#     prompt = (
#         f"You are a marketing expert. Return response STRICTLY in JSON format without markdown code blocks. "
#         'The JSON must have three keys: "email", "whatsapp", and "linkedin". '
#         f"\nCompany: {data.company}\nCampaign: {data.campaign}\nDescription: {data.description}"
#     )

#     payload = {
#         "contents": [{
#             "parts": [{"text": prompt}]
#         }]
#     }

#     try:
#         response = requests.post(GEMINI_URL, json=payload)
#         response_json = response.json()
#         print(response_json)
        
#         # Extract the text string from Gemini's nested structure
#         text_output = response_json['candidates'][0]['content']['parts'][0]['text']
        
#         # Clean the string in case Gemini adds ```json wrap
#         clean_text = text_output.replace("```json", "").replace("```", "").strip()
        
#         return json.loads(clean_text)
#     except Exception as e:
#         return {"error": str(e)}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=8000)