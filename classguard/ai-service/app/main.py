from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
from .classifier import ScreenClassifier

app = FastAPI(title="ClassGuard AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier = ScreenClassifier()


class ClassifyRequest(BaseModel):
    device_id: str
    image: Optional[str] = None
    window_title: Optional[str] = None
    browser_tabs: Optional[list[str]] = None


class ClassifyResponse(BaseModel):
    device_id: str
    status: str
    reason: Optional[str] = None
    confidence: float = 0.0


@app.post("/api/ai/classify", response_model=ClassifyResponse)
async def classify_screen(req: ClassifyRequest):
    if not req.image and not req.window_title:
        raise HTTPException(
            status_code=400,
            detail="At least one of image or window_title must be provided",
        )

    result = await classifier.classify(
        image_b64=req.image,
        window_title=req.window_title,
        browser_tabs=req.browser_tabs,
    )

    return ClassifyResponse(
        device_id=req.device_id,
        status=result["status"],
        reason=result.get("reason"),
        confidence=result.get("confidence", 0.0),
    )


@app.get("/api/ai/health")
async def health():
    return {"status": "ok"}
