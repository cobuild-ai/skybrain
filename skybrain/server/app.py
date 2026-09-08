import json
import time
import logging
import threading
from typing import List, Optional, Dict, Any, Generator, Union
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from skybrain.core.config import settings
from skybrain.engine.model_catalog import ModelCatalog, MODEL_PRESETS
from contextlib import asynccontextmanager
from skybrain.core.monitor import HostMemoryMonitor, BackgroundMemoryWatcher, SystemGuard, MemoryStatusLevel

logger = logging.getLogger("skybrain.server")

_catalog = ModelCatalog()
_llm_instance = None
_infer_lock = threading.Lock()
_memory_watcher: Optional[BackgroundMemoryWatcher] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _memory_watcher
    try:
        _memory_watcher = BackgroundMemoryWatcher(interval_seconds=15.0)
        _memory_watcher.start()
    except Exception as e:
        logger.warning(f"Failed to start BackgroundMemoryWatcher: {e}")
    try:
        yield
    finally:
        if _memory_watcher:
            _memory_watcher.stop()
            _memory_watcher = None
        close_llm()


app = FastAPI(title="SkyBrain OpenAI-Compatible API", version="0.1.0", lifespan=lifespan)


def close_llm():
    """Safely closes the active Llama instance and cleans up Metal GPU device buffers."""
    global _llm_instance
    if _llm_instance is not None:
        try:
            _llm_instance.close()
        except Exception as e:
            logger.debug(f"Error closing Llama instance: {e}")
        _llm_instance = None
        import gc
        gc.collect()


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
    mmproj_path = _catalog.get_mmproj_path()

    try:
        from llama_cpp import Llama
        chat_handler = None
        if mmproj_path and mmproj_path.exists():
            try:
                from llama_cpp.llama_chat_format import Qwen25VLChatHandler
                logger.info(f"📸 Initializing Qwen2.5 Vision Projector: {mmproj_path}")
                chat_handler = Qwen25VLChatHandler(clip_model_path=str(mmproj_path))
            except Exception as v_err:
                logger.warning(f"⚠️ Failed to load Qwen Vision handler ({v_err}), falling back to standard LLM.")

        from skybrain.core.hardware import HardwareAutoTuner, EnvironmentTier
        active_key = _catalog.get_active_key()
        assessment = HardwareAutoTuner.assess_environment(model_key=active_key)
        if assessment.tier == EnvironmentTier.INCOMPATIBLE:
            logger.critical(f"🛑 [Pre-flight Block] Incompatible environment: {assessment.message}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Incompatible Environment: {assessment.message}"
            )
        elif assessment.tier == EnvironmentTier.CONSTRAINED:
            logger.warning(f"⚠️ [Pre-flight Warning] Constrained environment: {assessment.message}")

        resolved_gpu_layers = settings.get_resolved_gpu_layers(model_key=active_key)
        logger.info(f"⚡ Loading LLM: {model_path} (GPU layers: {resolved_gpu_layers}, Vision: {chat_handler is not None})")
        _llm_instance = Llama(
            model_path=model_path,
            chat_handler=chat_handler,
            n_gpu_layers=resolved_gpu_layers,
            n_ctx=settings.n_ctx,
            n_threads=settings.n_threads,
            verbose=False
        )
        return _llm_instance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load Llama engine: {e}")
        _llm_instance = None
        raise HTTPException(status_code=500, detail=str(e))


class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Any]]


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
    mem = HostMemoryMonitor.get_memory_info()
    from skybrain.core.hardware import HardwareAutoTuner
    env = HardwareAutoTuner.assess_environment(model_key=active_key)
    return {
        "status": "healthy" if installed else "model_missing",
        "active_model": active_key,
        "model_installed": installed,
        "version": settings.version,
        "memory": mem.to_dict(),
        "environment": env.to_dict(),
    }


@app.get("/v1/system/environment")
def get_system_environment():
    from skybrain.core.hardware import HardwareAutoTuner
    active_key = _catalog.get_active_key()
    return HardwareAutoTuner.assess_environment(model_key=active_key).to_dict()


@app.get("/v1/system/memory")
def get_system_memory():
    return HostMemoryMonitor.get_memory_info().to_dict()


@app.get("/v1/models")
def list_models():
    models_data = []
    for m in _catalog.list_models():
        models_data.append({
            "id": m["key"],
            "object": "model",
            "created": int(time.time()),
            "owned_by": "skybrain",
            "root": m["key"],
            "description": m["description"],
            "active": m["active"],
            "installed": m["installed"],
        })
    return {"object": "list", "data": models_data}


def _stream_generator(messages: List[Dict[str, Any]], temperature: float = 0.3, max_tokens: int = 1024) -> Generator[str, None, None]:
    with _infer_lock:
        llm = get_llm()
        chunk_iter = llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        for chunk in chunk_iter:
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    global _llm_instance
    formatted_msgs = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        return StreamingResponse(
            _stream_generator(formatted_msgs, req.temperature or 0.3, req.max_tokens or 1024),
            media_type="text/event-stream"
        )

    with _infer_lock:
        llm = get_llm()
        try:
            response = llm.create_chat_completion(
                messages=formatted_msgs,
                temperature=req.temperature or 0.3,
                max_tokens=req.max_tokens or 1024
            )
            return response
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            # Reset corrupted instance so subsequent calls self-heal
            _llm_instance = None
            raise HTTPException(status_code=500, detail=str(e))
