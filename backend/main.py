from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, Form
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
import requests
import json
import os
import time
import base64
from io import BytesIO
from pypdf import PdfReader
from bs4 import BeautifulSoup

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
MIN_DOC_TEXT_LENGTH = 200
MIN_WEBSITE_TEXT_LENGTH = 300


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


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _fetch_website_text(website_url: str) -> tuple[str, str | None]:
    if not website_url:
        return "", None

    if not _is_valid_url(website_url):
        return "", "Website URL is invalid. Please enter a full URL like https://example.com."

    try:
        response = requests.get(
            website_url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MarketingAIPro/1.0)"},
        )
    except requests.RequestException as exc:
        return "", f"Unable to fetch website content: {exc}"

    if response.status_code >= 400:
        return "", f"Unable to fetch website content. Received HTTP {response.status_code}."

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    text = " ".join(soup.get_text(separator=" ").split())
    combined = f"{title}\n\n{text}".strip()

    if len(combined) < MIN_WEBSITE_TEXT_LENGTH:
        return "", (
            "Website content appears too short or blocked for scraping. "
            "Please share a different page URL or paste key website details in description."
        )

    return combined[:TEXT_PREVIEW_LIMIT], None


def _build_user_content(
    prompt: str,
    website_url: str | None,
    website_text: str,
    uploaded_file: UploadFile | None,
    file_bytes: bytes | None,
) -> tuple[list[dict], str | None]:
    context_chunks: list[str] = []
    if website_url and website_text:
        context_chunks.append(
            f"Website URL provided: {website_url}\n"
            "Use this website text as trusted business context:\n"
            f"{website_text}"
        )

    if uploaded_file and file_bytes:
        mime_type = uploaded_file.content_type or "application/octet-stream"
        file_name = uploaded_file.filename or "uploaded_file"

        if mime_type.startswith("image/"):
            encoded = base64.b64encode(file_bytes).decode("utf-8")
            prefix = (
                f"{prompt}\n\n"
                + ("\n\n".join(context_chunks) + "\n\n" if context_chunks else "")
                + f"An image file named '{file_name}' is attached. Analyze the image carefully and use it as additional campaign context."
            )
            return [
                {"type": "text", "text": prefix},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
            ], None

        extracted_text = _extract_text_from_file(file_name, file_bytes).strip()
        if extracted_text:
            if len(extracted_text) < MIN_DOC_TEXT_LENGTH:
                return [], (
                    "We could not extract enough readable text from the uploaded document. "
                    "Please upload a text-based PDF (not scanned), a clearer image, or paste key content into the description."
                )
            limited_text = extracted_text[:TEXT_PREVIEW_LIMIT]
            truncation_note = ""
            if len(extracted_text) > TEXT_PREVIEW_LIMIT:
                truncation_note = "\n\n[Note: Document content was truncated for token limits.]"
            context_chunks.append(
                f"Document attached: {file_name}\n"
                "Use this extracted text as trusted campaign context:\n"
                f"{limited_text}{truncation_note}"
            )
        else:
            return [], (
                f"The uploaded file '{file_name}' could not be parsed for usable content. "
                "Please upload a text PDF/image with readable text, or paste the relevant details into description."
            )

    if context_chunks:
        return [
            {
                "type": "text",
                "text": f"{prompt}\n\n" + "\n\n".join(context_chunks),
            }
        ], None

    return [{"type": "text", "text": prompt}], None


def _call_openai_with_retry(
    prompt: str,
    website_url: str | None = None,
    website_text: str = "",
    uploaded_file: UploadFile | None = None,
    file_bytes: bytes | None = None,
) -> dict:
    if not API_KEY:
        return {"error": "OPENAI_API_KEY is missing. Set it in environment variables."}

    last_error = "OpenAI did not return a valid response."
    user_content, content_error = _build_user_content(prompt, website_url, website_text, uploaded_file, file_bytes)
    if content_error:
        return {"error": content_error}

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior B2B marketing strategist. "
                    "Return only valid JSON with keys email, whatsapp, linkedin. "
                    "Each key must be an object with rich copy. "
                    "Do not invent facts not supported by provided context."
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.7,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "marketing_channels",
                "schema": {
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "object",
                            "properties": {
                                "subject": {"type": "string"},
                                "body": {"type": "string"},
                            },
                            "required": ["subject", "body"],
                            "additionalProperties": False,
                        },
                        "whatsapp": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                            },
                            "required": ["message"],
                            "additionalProperties": False,
                        },
                        "linkedin": {
                            "type": "object",
                            "properties": {
                                "post": {"type": "string"},
                            },
                            "required": ["post"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["email", "whatsapp", "linkedin"],
                    "additionalProperties": False,
                },
            },
        },
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
    website_url: str = Form(default=""),
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
        website_url = website_url.strip()
        website_text = ""
        if website_url:
            website_text, website_error = _fetch_website_text(website_url)
            if website_error:
                return {"error": website_error}

        file_bytes = None
        if file is not None:
            file_bytes = await file.read()
            if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                return {"error": "Uploaded file is too large. Please keep files under 10MB."}

        result = _call_openai_with_retry(
            prompt=prompt,
            website_url=website_url,
            website_text=website_text,
            uploaded_file=file,
            file_bytes=file_bytes,
        )

        choices = result.get("choices", [])
        if not choices:
            return {"error": result.get("error", "Invalid API response")}

        text_output = choices[0].get("message", {}).get("content", "")
        if not text_output:
            return {"error": "OpenAI returned an empty response."}

        clean_text = text_output.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
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




