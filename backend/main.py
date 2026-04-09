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
GEMINI_MODELS = [
    "gemini-2.5-flash",
]
RETRYABLE_ERROR_STATUSES = {"UNAVAILABLE", "RESOURCE_EXHAUSTED"}


def _extract_gemini_error(result: dict) -> tuple[str, str]:
    err = result.get("error", {})
    if isinstance(err, dict):
        return err.get("status", ""), err.get("message", "Invalid API response")
    return "", str(err or "Invalid API response")


def _is_retryable(status_code: int, error_status: str) -> bool:
    return status_code in {429, 500, 502, 503, 504} or error_status in RETRYABLE_ERROR_STATUSES


def _call_gemini_with_retry(payload: dict) -> dict:
    if not API_KEY:
        return {"error": "GEMINI_API_KEY is missing. Set it in environment variables."}

    last_error = "Gemini did not return a valid response."

    for model in GEMINI_MODELS:
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
        for attempt in range(3):
            try:
                response = requests.post(gemini_url, json=payload, timeout=45)
                try:
                    result = response.json()
                except ValueError:
                    result = {"error": {"message": f"Non-JSON response from Gemini ({response.status_code})."}}

                if response.ok and "candidates" in result:
                    return result

                error_status, error_message = _extract_gemini_error(result)
                last_error = f"{error_message} (model={model})"

                if not _is_retryable(response.status_code, error_status):
                    break

                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
            except requests.RequestException as exc:
                last_error = f"Network error calling Gemini: {exc}"
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

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        result = _call_gemini_with_retry(payload)

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


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=8000)




