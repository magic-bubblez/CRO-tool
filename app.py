import os
import tempfile
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pipeline.orchestrator import run_pipeline

app = FastAPI(title="CRO Enhancement Tool")

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")

# In-memory store for enhanced pages
enhanced_pages = {}


@app.post("/api/enhance")
async def enhance_page(
    url: str = Form(...),
    ad_creative: UploadFile = File(...),
):
    """Run the CRO enhancement pipeline."""
    if not GEMINI_KEY and not GROQ_KEY and not OPENROUTER_KEY:
        raise HTTPException(status_code=500, detail="No API keys set. Add GEMINI_API_KEY, GROQ_API_KEY, and/or OPENROUTER_API_KEY to .env")

    if not ad_creative.filename:
        raise HTTPException(status_code=422, detail="Please upload an ad creative image")

    ad_creative_path = None
    try:
        suffix = os.path.splitext(ad_creative.filename)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await ad_creative.read()
            tmp.write(content)
            ad_creative_path = tmp.name

        result = await run_pipeline(
            url=url,
            gemini_key=GEMINI_KEY,
            groq_key=GROQ_KEY,
            openrouter_key=OPENROUTER_KEY,
            ad_creative_path=ad_creative_path,
        )

        page_id = str(uuid.uuid4())[:8]
        enhanced_pages[page_id] = result["enhanced_html"]

        original_id = str(uuid.uuid4())[:8]
        enhanced_pages[original_id] = result["original_html"]

        return {
            "enhanced_page_id": page_id,
            "original_page_id": original_id,
            "report": result["report"],
            "raw_plan": result["raw_plan"],
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if ad_creative_path and os.path.exists(ad_creative_path):
            os.unlink(ad_creative_path)


@app.get("/page/{page_id}")
async def serve_page(page_id: str):
    """Serve a stored HTML page — used by iframes."""
    html = enhanced_pages.get(page_id)
    if not html:
        raise HTTPException(status_code=404, detail="Page not found")
    return HTMLResponse(content=html)


@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")


app.mount("/static", StaticFiles(directory="frontend"), name="static")
