from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, Form
from dotenv import load_dotenv
from pathlib import Path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
import requests
import json
import os
import time
import base64
from io import BytesIO
from pypdf import PdfReader

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
# OpenAI Config
# -------------------------
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
TEXT_PREVIEW_LIMIT = 12000


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        chunks = []
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                chunks.append(text)
        return "\n\n".join(chunks)
    except Exception:
        return ""


def _extract_text_from_file(file_name: str, file_bytes: bytes) -> str:
    suffix = Path(file_name or "").suffix.lower()

    if suffix == ".pdf":
        return _extract_text_from_pdf(file_bytes)

    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1")
        except UnicodeDecodeError:
            return ""


def _build_user_content(prompt: str, uploaded_file: UploadFile | None, file_bytes: bytes | None) -> list[dict]:
    if not uploaded_file or not file_bytes:
        return [{"type": "text", "text": prompt}]

    mime_type = uploaded_file.content_type or "application/octet-stream"
    file_name = uploaded_file.filename or "uploaded_file"

    if mime_type.startswith("image/"):
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        return [
            {
                "type": "text",
                "text": (
                    f"{prompt}\n\n"
                    f"An image file named '{file_name}' is attached. Analyze it and use it as additional campaign context."
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
            },
        ]

    extracted_text = _extract_text_from_file(file_name, file_bytes).strip()
    if extracted_text:
        limited_text = extracted_text[:TEXT_PREVIEW_LIMIT]
        truncation_note = ""
        if len(extracted_text) > TEXT_PREVIEW_LIMIT:
            truncation_note = "\n\n[Note: Document content was truncated for token limits.]"
        return [
            {
                "type": "text",
                "text": (
                    f"{prompt}\n\n"
                    f"Document attached: {file_name}\n"
                    "Use the following extracted text as additional context:\n\n"
                    f"{limited_text}{truncation_note}"
                ),
            }
        ]

    return [
        {
            "type": "text",
            "text": (
                f"{prompt}\n\n"
                f"A file named '{file_name}' was uploaded, but text extraction was not possible. "
                "Proceed using the user-provided form description."
            ),
        }
    ]


def _call_openai_with_retry(prompt: str, uploaded_file: UploadFile | None = None, file_bytes: bytes | None = None) -> dict:
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
            {"role": "user", "content": _build_user_content(prompt, uploaded_file, file_bytes)},
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
async def generate_marketing_content(
    company: str = Form(...),
    campaign: str = Form(...),
    description: str = Form(...),
    file: UploadFile | None = File(default=None),
):

    prompt = (
        "You are a marketing expert. Return ONLY valid JSON (no markdown). "
        'Keys: "email", "whatsapp", "linkedin".\n\n'
        f"Company: {company}\n"
        f"Campaign: {campaign}\n"
        f"Description: {description}"
    )

    try:
        file_bytes = None
        if file is not None:
            file_bytes = await file.read()
            if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                return {"error": "Uploaded file is too large. Please keep files under 10MB."}

        result = _call_openai_with_retry(prompt, file, file_bytes)

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




