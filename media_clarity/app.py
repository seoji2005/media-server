"""Loopback HTTP boundary and bounded byte-range playback."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from .jobs import Jobs
from .model_check import configuration as model_configuration, diagnose as diagnose_models
from .recommendations import Recommendations
from .subtitles import MAX_SUBTITLE_BYTES

from .storage import CHUNK, MediaError, Store, default_data_dir, safe_io, title_from_name


STATIC = Path(__file__).parent / "static"
ASSETS = {"app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class ManagedStreamingResponse(StreamingResponse):
    def __init__(self, content, verified, **kwargs):
        self.verified = verified
        super().__init__(content, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # Also covers disconnect/cancellation before the body generator starts.
            self.verified.close()


def byte_range(header: str | None, size: int) -> tuple[int, int, int]:
    if header is None:
        return 0, size - 1, 200
    if len(header) > 120 or not re.fullmatch(r"bytes=(\d*)-(\d*)", header):
        raise MediaError("invalid_range", 416)
    first, last = header[6:].split("-")
    if not first:
        if not last or int(last) <= 0:
            raise MediaError("invalid_range", 416)
        return max(0, size - int(last)), size - 1, 206
    start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise MediaError("invalid_range", 416)
    return start, end, 206


def create_app(data_dir: Path | None = None) -> FastAPI:
    from .previews import Previews
    store = Store(data_dir if data_dir is not None else default_data_dir())
    jobs = Jobs(store)
    recommendations = Recommendations(store)
    previews = Previews(store)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        store.start()
        try:
            recommendations.init()
            jobs.start()
            yield
        finally:
            previews.close()
            jobs.close()
            store.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.jobs = jobs
    app.state.previews = previews

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        host = request.headers.get("host", "").lower()
        valid_host = re.fullmatch(r"(127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?", host)
        origin = request.headers.get("origin")
        denied = not valid_host or (origin is not None and origin != "http://" + host) or request.headers.get("sec-fetch-site") == "cross-site"
        if denied:
            response = JSONResponse({"error": "local_origin_required"}, status_code=403)
        elif request.method not in {"GET", "HEAD", "OPTIONS"} and not secrets.compare_digest(request.headers.get("x-media-token", ""), token):
            response = JSONResponse({"error": "session_required"}, status_code=403)
        else:
            try:
                response = await call_next(request)
            except MediaError as exc:
                response = JSONResponse({"error": exc.code}, status_code=exc.status)
            except (OSError, sqlite3.Error):
                response = JSONResponse({"error": "storage_unavailable"}, status_code=503)
            except Exception:
                # No request body, URL, source name, decoder output or traceback in logs.
                response = JSONResponse({"error": "internal_error"}, status_code=500)
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.exception_handler(MediaError)
    async def media_error(request, exc):
        return JSONResponse({"error": exc.code}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.get("/")
    def index():
        return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))

    @app.get("/assets/{name}")
    def asset(name: str):
        # Exact filenames only; no StaticFiles path resolving/UNC handling.
        if name not in ASSETS:
            raise MediaError("asset_not_found", 404)
        return Response((STATIC / name).read_bytes(), media_type=ASSETS[name])

    @app.get("/api/session")
    def session():
        return {"token": token, "diagnostics": {**store.diagnostics(), 'models':model_configuration(store.root)}}

    @app.post("/api/models/diagnostics")
    def model_diagnostics():
        # Reuse the supervisor lock and kernel lease: no diagnostic CUDA context
        # beside active/orphan inference, and queued work waits without being lost.
        if not jobs.lock.acquire(blocking=False):
            raise MediaError('processing_worker_active', 409)
        try:
            if jobs.process and jobs.process.poll() is None:
                raise MediaError('processing_worker_active', 409)
            return diagnose_models(store.root)
        finally:
            jobs.lock.release()

    @app.get("/api/library")
    def library():
        return {"items": store.list_items()}

    @app.post('/api/library/{item_id}/playback')
    def prepare_playback(item_id: str):
        from .renditions import prepare
        return prepare(store, item_id)

    @app.post('/api/library/{item_id}/audio/{audio_index}')
    def select_audio(item_id: str, audio_index: int):
        from .renditions import prepare
        return prepare(store, item_id, audio_index)

    @app.get("/api/library/{item_id}")
    def item(item_id: str):
        return store.item(item_id)

    @app.get('/api/library/{item_id}/previews')
    def preview_status(item_id: str):
        return previews.status(item_id)

    @app.post('/api/library/{item_id}/previews')
    def prepare_previews(item_id: str):
        return previews.prepare(item_id)

    @app.post('/api/library/{item_id}/previews/{ordinal}/retry')
    def retry_preview(item_id: str, ordinal: int):
        return previews.prepare(item_id, retry=ordinal)

    @app.get('/api/library/{item_id}/previews/{set_id}/{ordinal}.jpg')
    def preview_image(item_id: str, set_id: str, ordinal: int):
        data, digest = previews.image(item_id,set_id,ordinal)
        return Response(data, media_type='image/jpeg', headers={'ETag':'"'+digest+'"'})

    @app.get("/api/recommendations")
    def suggested_items():
        return recommendations.suggest()

    @app.get("/api/library/{item_id}/preference")
    def item_preference(item_id: str):
        return recommendations.preference(item_id)

    @app.put("/api/library/{item_id}/preference")
    async def save_preference(item_id: str, request: Request):
        payload = bytearray()
        async for chunk in request.stream():
            if len(payload) + len(chunk) > 256:
                raise MediaError('invalid_request', 422)
            payload.extend(chunk)
        try:
            body = json.loads(payload)
        except (ValueError, UnicodeError):
            raise MediaError('invalid_request', 422) from None
        if type(body) is not dict or set(body) != {'included', 'preference', 'revision'}:
            raise MediaError('invalid_request', 422)
        return await run_in_threadpool(recommendations.save, item_id, body['included'], body['preference'], body['revision'])

    @app.post("/api/import")
    async def import_video(request: Request):
        if request.headers.get("content-type", "").split(";")[0] != "application/octet-stream":
            raise MediaError("binary_upload_required", 415)
        if not store.import_lock.acquire(blocking=False):
            raise MediaError("import_busy", 409)
        stage, output = None, None
        try:
            length = request.headers.get("content-length")
            if length is not None and (not re.fullmatch(r"\d{1,20}", length) or int(length) <= 0):
                raise MediaError("empty_media", 422)
            if length:
                store.ensure_space(int(length))
            name = request.headers.get("x-media-filename", "video")
            if len(name) > 3000:
                raise MediaError("invalid_request", 422)
            title = title_from_name(unquote(name))
            stage, output = await run_in_threadpool(store.new_stage)
            digest, size = hashlib.sha256(), 0
            async for incoming in request.stream():
                for offset in range(0, len(incoming), CHUNK):
                    chunk = incoming[offset:offset + CHUNK]
                    await run_in_threadpool(store.ensure_space, len(chunk))
                    await run_in_threadpool(output.write, chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if length is not None and size != int(length):
                raise MediaError("incomplete_upload", 422)
            await run_in_threadpool(output.flush)
            await run_in_threadpool(os.fsync, output.fileno())
            output.close()
            output = None
            result = await run_in_threadpool(store.finish_import, stage, digest.hexdigest(), size, title)
            return JSONResponse(result, status_code=200 if result["duplicate"] else 201)
        except ClientDisconnect:
            raise MediaError("incomplete_upload", 422) from None
        except OSError as exc:
            raise safe_io(exc) from None
        finally:
            try:
                if output is not None:
                    output.close()
                if stage is not None:
                    store.remove_stage(stage)
            finally:
                store.import_lock.release()

    @app.put("/api/library/{item_id}/position")
    async def save_position(item_id: str, request: Request):
        # Read a tiny, bounded document; bool/NaN/Infinity never count as positions.
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 256:
                raise MediaError("invalid_request", 422)
        try:
            body = json.loads(payload)
        except (ValueError, UnicodeError):
            raise MediaError("invalid_request", 422) from None
        if type(body) is not dict or set(body) not in ({"position"}, {"position","audio_index"}):
            raise MediaError("invalid_request", 422)
        return await run_in_threadpool(store.save_position, item_id, body["position"], body.get('audio_index'))

    @app.get("/api/library/{item_id}/subtitles")
    def subtitles(item_id: str):
        return jobs.status(item_id)

    @app.post("/api/library/{item_id}/subtitles")
    async def import_subtitles(item_id: str, request: Request, audio_index: int | None = None):
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_SUBTITLE_BYTES:
                raise MediaError("subtitles_too_large", 413)
            data.extend(chunk)
        track_id = await run_in_threadpool(jobs.import_srt, item_id, bytes(data), audio_index)
        return JSONResponse({"id":track_id}, status_code=201)

    @app.get("/api/library/{item_id}/subtitles/{track_id}.vtt")
    def subtitle_content(item_id: str, track_id: str):
        return Response(jobs.track(item_id, track_id), media_type="text/vtt; charset=utf-8")

    @app.post("/api/library/{item_id}/subtitle-jobs")
    def create_subtitle_job(item_id: str, audio_index: int | None = None):
        return JSONResponse({"id":jobs.enqueue(item_id, audio_index=audio_index)}, status_code=202)

    @app.post("/api/library/{item_id}/subtitle-jobs/regenerate")
    def regenerate_subtitle_job(item_id: str, audio_index: int | None = None):
        # A new version; existing supplied/generated tracks remain available.
        return JSONResponse({"id":jobs.enqueue(item_id, force=True, audio_index=audio_index)}, status_code=202)

    @app.post("/api/subtitle-jobs/{job_id}/{action}")
    def subtitle_job_action(job_id: str, action: str):
        jobs.action(job_id, action)
        return {"ok":True}

    @app.api_route("/api/media/{item_id}/content", methods=["GET", "HEAD"])
    def content(item_id: str, request: Request, audio_index: int | None = None):
        row = store.playback_row(item_id, audio_index)
        verified = store.open_verified(row)
        size = row["size"]
        etag = '"' + row["sha256"] + '"'
        range_header = request.headers.get("range")
        if request.headers.get("if-range") not in {None, etag}:
            range_header = None
        try:
            start, end, status = byte_range(range_header, size)
        except MediaError:
            verified.close()
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1), "ETag": etag}
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        if request.method == "HEAD":
            verified.close()
            return Response(status_code=status, media_type=row["mime"], headers=headers)

        # Prime the first block before headers: a detected change is a JSON 409.
        # A new change after headers aborts the stream before any changed block
        # is emitted; already-sent successful status cannot then become a 409.
        blocks = verified.read_range(start, end)
        try:
            first = next(blocks)
        except BaseException:
            verified.close()
            raise

        def chunks():
            try:
                yield first
                yield from blocks
            finally:
                blocks.close()
                verified.close()
        return ManagedStreamingResponse(chunks(), verified, status_code=status,
                                        media_type=row["mime"], headers=headers)

    @app.get("/api/media/{item_id}/thumbnail")
    def thumbnail(item_id: str):
        row = store._row(item_id)
        if not row["thumbnail"]:
            raise MediaError("thumbnail_unavailable", 404)
        path = store.file_path(row, thumbnail=True)
        if path.stat().st_size > 2 * 1024 * 1024:
            raise MediaError("thumbnail_unavailable", 404)
        return Response(path.read_bytes(), media_type="image/jpeg")

    return app
