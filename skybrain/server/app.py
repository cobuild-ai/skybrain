import json
import time
import logging
import threading
from typing import List, Optional, Dict, Any, Generator
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from skybrain.core.config import settings
from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS

logger = logging.getLogger("skybrain.server")
app = FastAPI(title="SkyBrain OpenAI-Compatible API", version="0.1.0")

_catalog = ModelCatalog()
_llm_instance = None
_infer_lock = threading.Lock()


def get_llm(force_reload: bool = False):
    global _llm_instance
    if _llm_instance is not None and not force_reload:
        return _llm_instance
    
    if not _catalog.is_installed():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Active model is not downloaded. Run 'skybrain model download' first."
        )
    
    model_path = str(_catalog.get_model_path())
    try:
        from llama_cpp import Llama
        logger.info(f"⚡ Loading Metal LLM: {model_path}")
        _llm_instance = Llama(
            model_path=model_path,
            n_gpu_layers=settings.n_gpu_layers,
            n_ctx=settings.n_ctx,
            n_threads=settings.n_threads,
            verbose=False
        )
        return _llm_instance
    except Exception as e:
        logger.error(f"Failed to load Llama engine: {e}")
        _llm_instance = None
        raise HTTPException(status_code=500, detail=str(e))


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "default"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False


@app.get("/healthz")
def healthz():
    active_key = _catalog.get_active_key()
    installed = _catalog.is_installed(active_key)
    return {
        "status": "healthy" if installed else "model_missing",
        "active_model": active_key,
        "model_installed": installed,
        "version": settings.version
    }


@app.get("/v1/models")
def list_models():
    models_data = []
    for m in _catalog.list_models():
        models_data.append({
            "id": m["key"],
            "object": "model",
            "created": int(time.time()),
            "owned_by": "skybrain",
            "root": m["filename"],
            "description": m["description"],
            "active": m["active"],
            "installed": m["installed"]
        })
    return {"object": "list", "data": models_data}


def _stream_generator(formatted_msgs, temperature, max_tokens) -> Generator[str, None, None]:
    global _llm_instance
    with _infer_lock:
        llm = get_llm()
        try:
            stream_response = llm.create_chat_completion(
                messages=formatted_msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            for chunk in stream_response:
                payload = f"data: {json.dumps(chunk)}\n\n"
                yield payload
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming completion error: {e}")
            _llm_instance = None
            yield f"data: {json.dumps({'error': str(e)})}\n\n"


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    global _llm_instance
    formatted_msgs = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        return StreamingResponse(
            _stream_generator(formatted_msgs, req.temperature, req.max_tokens),
            media_type="text/event-stream"
        )

    with _infer_lock:
        llm = get_llm()
        try:
            response = llm.create_chat_completion(
                messages=formatted_msgs,
                temperature=req.temperature,
                max_tokens=req.max_tokens
            )
            return response
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            # Reset corrupted instance so subsequent calls self-heal
            _llm_instance = None
            raise HTTPException(status_code=500, detail=str(e))
