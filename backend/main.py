from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
import requests
import json
import os
import time

# -------------------------
# Setup
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

API_KEY = os.getenv("OPENAI_API_KEY")

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
# OpenAI Config
# -------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _call_openai_with_retry(prompt: str) -> dict:
    if not API_KEY:
        return {"error": "OPENAI_API_KEY is missing. Set it in environment variables."}

    last_error = "OpenAI did not return a valid response."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a marketing expert. Return ONLY valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            try:
                result = response.json()
            except ValueError:
                result = {"error": {"message": f"Non-JSON response from OpenAI ({response.status_code})."}}

            if response.ok:
                return result

            error_obj = result.get("error", {}) if isinstance(result, dict) else {}
            error_message = error_obj.get("message", "Invalid API response")
            last_error = f"{error_message} (model={OPENAI_MODEL})"

            if response.status_code not in {429, 500, 502, 503, 504}:
                break

            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
        except requests.RequestException as exc:
            last_error = f"Network error calling OpenAI: {exc}"
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))

    return {"error": last_error}

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

    try:
        result = _call_openai_with_retry(prompt)

        choices = result.get("choices", [])
        if not choices:
            return {"error": result.get("error", "Invalid API response")}

        text_output = choices[0].get("message", {}).get("content", "")
        if not text_output:
            return {"error": "OpenAI returned an empty response."}

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


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=8000)




