from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False

from google import genai
from google.genai import types as gtypes

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE        = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config_key(key: str, value) -> None:
    try:
        cfg = _load_config()
        cfg[key] = value
        _CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"[Vision] ⚠️  Could not save config key '{key}': {e}")


def _get_api_key() -> str:
    key = _load_config().get("gemini_api_key", "")
    if not key:
        raise RuntimeError("gemini_api_key not found in config.")
    return key


def _get_os() -> str:
    cfg_os = _load_config().get("os_system")
    if cfg_os:
        return str(cfg_os).lower()
    return platform.system().lower()

_LIVE_MODEL         = "models/gemini-2.5-flash-native-audio-preview-12-2025"
_CHANNELS           = 1
_RECEIVE_SAMPLE_RATE = 24_000
_CHUNK_SIZE         = 1_024

_IMG_MAX_W = 1280
_IMG_MAX_H = 720
_JPEG_Q    = 82

_SYSTEM_PROMPT = (
    "You are MJ, the user's AI assistant. "
    "You are given an image from either the user's screen or their webcam. "
    "Analyze what you see with detail and intelligence. "
    "Describe objects, text, people, components, and their context clearly. "
    "For technical questions (circuits, code, hardware) give specific, expert answers. "
    "Be concise — 2-4 sentences — unless the question demands more detail. "
    "Speak directly to the user ('I can see...', 'You have...'). "
    "Address the user as 'sir' depending on the language they used."
)


def _compress(img_bytes: bytes, source_format: str = "PNG") -> tuple[bytes, str]:
    if not _PIL:
        return img_bytes, f"image/{source_format.lower()}"

    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q, optimize=False)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"[Vision] ⚠️  Image compress failed: {e}")
        return img_bytes, f"image/{source_format.lower()}"

def _capture_screen_wayland() -> Optional[bytes]:
    """Captures real screen under Linux Wayland using XDG Desktop Portal & DBus."""
    pictures_dir = Path.home() / "Pictures"
    before_files = set(pictures_dir.glob("Screenshot*.png")) | set((pictures_dir / "Screenshots").glob("*.png"))
    
    cmd = [
        "gdbus", "call", "--session",
        "--dest", "org.freedesktop.portal.Desktop",
        "--object-path", "/org/freedesktop/portal/desktop",
        "--method", "org.freedesktop.portal.Screenshot.Screenshot",
        "", '{"interactive": <false>}'
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        for _ in range(15):
            time.sleep(0.1)
            after_files = set(pictures_dir.glob("Screenshot*.png")) | set((pictures_dir / "Screenshots").glob("*.png"))
            new_files = list(after_files - before_files)
            if new_files:
                latest = max(new_files, key=lambda p: p.stat().st_mtime)
                if latest.stat().st_size > 1000:
                    data = latest.read_bytes()
                    try:
                        latest.unlink()
                    except Exception:
                        pass
                    return data

        all_files = list(pictures_dir.glob("Screenshot*.png")) + list((pictures_dir / "Screenshots").glob("*.png"))
        if all_files:
            latest = max(all_files, key=lambda p: p.stat().st_mtime)
            if time.time() - latest.stat().st_mtime < 4.0 and latest.stat().st_size > 1000:
                data = latest.read_bytes()
                try:
                    latest.unlink()
                except Exception:
                    pass
                return data
    except Exception as e:
        print(f"[Vision] ⚠️ Wayland portal capture failed: {e}")

    # Tool fallbacks (grim / gnome-screenshot / scrot)
    for tool_cmd, is_file in [
        (["grim", "-"], False),
        (["gnome-screenshot", "-f", "/tmp/_mj_shot.png"], True),
        (["scrot", "/tmp/_mj_shot.png"], True),
    ]:
        if shutil.which(tool_cmd[0]):
            try:
                if is_file:
                    subprocess.run(tool_cmd, capture_output=True, timeout=3)
                    if os.path.exists("/tmp/_mj_shot.png"):
                        data = open("/tmp/_mj_shot.png", "rb").read()
                        os.remove("/tmp/_mj_shot.png")
                        return data
                else:
                    r = subprocess.run(tool_cmd, capture_output=True, timeout=3)
                    if r.returncode == 0 and len(r.stdout) > 1000:
                        return r.stdout
            except Exception:
                pass
    return None


def _capture_screen() -> tuple[bytes, str]:
    is_linux_wayland = (
        platform.system().lower() == "linux"
        and os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )

    if is_linux_wayland:
        wayland_bytes = _capture_screen_wayland()
        if wayland_bytes:
            return _compress(wayland_bytes, "PNG")

    if not _MSS:
        if platform.system().lower() == "linux":
            wayland_bytes = _capture_screen_wayland()
            if wayland_bytes:
                return _compress(wayland_bytes, "PNG")
        raise RuntimeError("mss is not installed. Run: pip install mss")

    try:
        with mss.mss() as sct:
            monitors = sct.monitors          # [0] = all combined, [1..n] = real screens
            target   = monitors[1] if len(monitors) > 1 else monitors[0]
            shot     = sct.grab(target)
            png      = mss.tools.to_png(shot.rgb, shot.size)

        # Check if MSS captured an all-black screen (common Wayland artifact)
        if _PIL and platform.system().lower() == "linux":
            try:
                test_img = PIL.Image.open(io.BytesIO(png)).convert("L")
                test_arr = np.array(test_img)
                if test_arr.mean() < 1.0:
                    print("[Vision] ⚠️ MSS captured solid black screen on Linux. Falling back to Wayland portal...")
                    wayland_bytes = _capture_screen_wayland()
                    if wayland_bytes:
                        return _compress(wayland_bytes, "PNG")
            except Exception:
                pass

        return _compress(png, "PNG")
    except Exception as e:
        if platform.system().lower() == "linux":
            wayland_bytes = _capture_screen_wayland()
            if wayland_bytes:
                return _compress(wayland_bytes, "PNG")
        raise e


def _cv2_backend() -> int:
    """Return the best OpenCV camera backend for the current OS."""
    if not _CV2:
        return 0
    os_name = _get_os()
    if os_name == "windows":
        return cv2.CAP_DSHOW    
    if os_name == "mac":
        return cv2.CAP_AVFOUNDATION  
    return cv2.CAP_ANY


def _is_green_buffer(frame) -> bool:
    """Detect uninitialized YUV V4L2 buffers (which decode to solid green in RGB)."""
    if frame is None or frame.size == 0:
        return True
    b_mean = float(frame[:, :, 0].mean())
    g_mean = float(frame[:, :, 1].mean())
    r_mean = float(frame[:, :, 2].mean())
    # Uninitialized YUV buffer in V4L2 maps to high G (>80) with low R & B (<25)
    return bool(g_mean > 80 and r_mean < 25 and b_mean < 25)


def _probe_camera(index: int, backend: int, warmup: int = 15) -> bool:
    if not _CV2:
        return False
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened() and backend != cv2.CAP_ANY:
        cap.release()
        cap = cv2.VideoCapture(index, cv2.CAP_ANY)
    if not cap.isOpened():
        return False

    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    except Exception:
        pass

    valid_frame = None
    for _ in range(warmup):
        ret, frame = cap.read()
        if ret and frame is not None and not _is_green_buffer(frame):
            valid_frame = frame
            break
        time.sleep(0.04)

    cap.release()
    if valid_frame is None:
        return False
    return bool(float(np.mean(valid_frame)) > 8)


def _detect_camera_index() -> int:

    backend = _cv2_backend()
    print("[Vision] 🔍 Auto-detecting camera...")
    for idx in range(6):
        if _probe_camera(idx, backend):
            print(f"[Vision] ✅ Camera found at index {idx}")
            _save_config_key("camera_index", idx)
            return idx
        print(f"[Vision] ⚠️  Camera index {idx}: no usable frame")

    print("[Vision] ⚠️  No camera found — defaulting to index 0")
    _save_config_key("camera_index", 0)
    return 0


def _get_camera_index() -> int:
    cfg = _load_config()
    if "camera_index" in cfg:
        return int(cfg["camera_index"])
    return _detect_camera_index()


def _camera_photo_folder() -> Path:
    """Returns the dedicated Photos/MJ folder (creates it if missing)."""
    project_photos = _BASE / "Photos" / "MJ"
    project_photos.mkdir(parents=True, exist_ok=True)
    try:
        home_photos = Path.home() / "Photos" / "MJ"
        home_photos.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return project_photos


_LAST_CAMERA_PHOTO_PATH: Path | None = None


def _save_camera_photo(image_bytes: bytes) -> Path:
    """Saves clicked photo into Photos/MJ folder."""
    global _LAST_CAMERA_PHOTO_PATH
    folder = _camera_photo_folder()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"mj_photo_{timestamp}.jpg"
    file_path = folder / file_name
    file_path.write_bytes(image_bytes)

    try:
        home_path = Path.home() / "Photos" / "MJ" / file_name
        home_path.write_bytes(image_bytes)
    except Exception:
        pass

    _LAST_CAMERA_PHOTO_PATH = file_path
    print(f"[Camera] 📸 Photo saved to: {file_path}")
    return file_path


def get_last_camera_photo() -> tuple[bytes, Path] | None:
    global _LAST_CAMERA_PHOTO_PATH
    if _LAST_CAMERA_PHOTO_PATH and _LAST_CAMERA_PHOTO_PATH.exists():
        data = _LAST_CAMERA_PHOTO_PATH.read_bytes()
        return data, _LAST_CAMERA_PHOTO_PATH
    folder = _camera_photo_folder()
    files = sorted(
        folder.glob("mj_photo_*.jpg"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return None
    data = files[0].read_bytes()
    _LAST_CAMERA_PHOTO_PATH = files[0]
    return data, files[0]


def show_last_camera_photo(player=None) -> str:
    last = get_last_camera_photo()
    if not last:
        return "No saved camera photo found in Photos/MJ."
    image_bytes, path = last
    if player and hasattr(player, "show_camera_frame"):
        try:
            player.show_camera_frame(image_bytes)
        except Exception as e:
            print(f"[Vision] ⚠️  Could not preview last photo: {e}")
            return f"Could not display last photo: {e}"
    return f"Showing last photo from Photos/MJ: {path}"


def take_photo(player=None) -> str:
    """Explicitly clicks a photo from camera and saves it into Photos/MJ."""
    try:
        img_bytes, mime = _capture_camera(save_to_disk=False)
        saved_path = _save_camera_photo(img_bytes)
        if player and hasattr(player, "show_camera_frame"):
            try:
                player.show_camera_frame(img_bytes)
            except Exception as e:
                print(f"[Vision] Preview warning: {e}")
        return f"📸 Photo clicked successfully and saved to Photos/MJ ({saved_path.name})"
    except Exception as e:
        return f"Failed to click photo: {e}"


def _capture_camera(save_to_disk: bool = False) -> tuple[bytes, str]:
    if not _CV2:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    index   = _get_camera_index()
    backend = _cv2_backend()
    cap     = cv2.VideoCapture(index, backend)
    if not cap.isOpened() and backend != cv2.CAP_ANY:
        cap.release()
        cap = cv2.VideoCapture(index, cv2.CAP_ANY)

    if not cap.isOpened():
        cap.release()
        raise RuntimeError(
            f"Camera index {index} could not be opened. "
            "Try setting camera_index in config or ensure the webcam is connected."
        )

    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    except Exception:
        pass

    target_frame = None
    last_frame = None
    for _ in range(25):
        ret, frame = cap.read()
        if ret and frame is not None:
            last_frame = frame
            if not _is_green_buffer(frame):
                target_frame = frame
                break
        time.sleep(0.04)

    cap.release()

    frame = target_frame if target_frame is not None else last_frame
    if frame is None:
        raise RuntimeError("Camera returned no frame. Check that the webcam is not used by another app.")

    if _PIL:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q)
        img_bytes = buf.getvalue()
        if save_to_disk:
            _save_camera_photo(img_bytes)
        return img_bytes, "image/jpeg"

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_Q])
    img_bytes = buf.tobytes()
    if save_to_disk:
        _save_camera_photo(img_bytes)
    return img_bytes, "image/jpeg"

class _VisionSession:
    def __init__(self):
        self._loop:       Optional[asyncio.AbstractEventLoop] = None
        self._thread:     Optional[threading.Thread]          = None
        self._session                                          = None
        self._out_queue:  Optional[asyncio.Queue]             = None
        self._audio_in:   Optional[asyncio.Queue]             = None
        self._ready_evt:  threading.Event                     = threading.Event()
        self._player                                           = None
        self._lock:       threading.Lock                       = threading.Lock()

    def start(self, player=None, timeout: float = 25.0) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                if player is not None:
                    self._player = player
                return
            self._player = player
            self._thread = threading.Thread(
                target=self._run_event_loop,
                daemon=True,
                name="VisionSessionThread",
            )
            self._thread.start()

        if not self._ready_evt.wait(timeout=timeout):
            raise RuntimeError(f"Vision session did not connect within {timeout}s.")
        print("[Vision] ✅ Session ready")

    def analyze(self, image_bytes: bytes, mime_type: str, user_text: str) -> None:
        if not self._loop or not self._out_queue:
            print("[Vision] ⚠️  Session not started — dropping request")
            return
        asyncio.run_coroutine_threadsafe(
            self._out_queue.put((image_bytes, mime_type, user_text)),
            self._loop,
        )

    def is_ready(self) -> bool:
        return self._session is not None

    def _run_event_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._session_loop())

    async def _session_loop(self) -> None:
        self._out_queue = asyncio.Queue(maxsize=30)
        self._audio_in  = asyncio.Queue()

        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"},
        )
        config = gtypes.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            system_instruction=_SYSTEM_PROMPT,
            speech_config=gtypes.SpeechConfig(
                voice_config=gtypes.VoiceConfig(
                    prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(
                        voice_name="Aoede"
                    )
                )
            ),
        )

        backoff = 2.0
        while True:
            try:
                print("[Vision] 🔌 Connecting...")
                async with client.aio.live.connect(
                    model=_LIVE_MODEL, config=config
                ) as session:
                    self._session = session
                    self._ready_evt.set()
                    backoff = 2.0  
                    print("[Vision] ✅ Connected")

                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._send_loop())
                        tg.create_task(self._recv_loop())
                        tg.create_task(self._play_loop())

            except* Exception as eg:
                for exc in eg.exceptions:
                    print(f"[Vision] ⚠️  Session error: {exc}")
            finally:
                self._session = None
                self._ready_evt.clear()

            print(f"[Vision] 🔄 Reconnecting in {backoff:.0f}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)
            self._ready_evt.set()  

    async def _send_loop(self) -> None:
        while True:
            image_bytes, mime_type, user_text = await self._out_queue.get()
            if not self._session:
                print("[Vision] ⚠️  No session — dropping image")
                continue
            try:
                b64 = base64.b64encode(image_bytes).decode("ascii")
                await self._session.send_client_content(
                    turns={
                        "parts": [
                            {"inline_data": {"mime_type": mime_type, "data": b64}},
                            {"text": user_text},
                        ]
                    },
                    turn_complete=True,
                )
                print(f"[Vision] 📤 Sent {len(image_bytes):,} bytes — '{user_text[:60]}'")
            except Exception as e:
                print(f"[Vision] ⚠️  Send error: {e}")
                raise  # propagate to TaskGroup → triggers session reconnect

    async def _recv_loop(self) -> None:
        transcript: list[str] = []
        try:
            async for response in self._session.receive():
                if response.data:
                    await self._audio_in.put(response.data)

                sc = response.server_content
                if not sc:
                    continue

                if sc.output_transcription and sc.output_transcription.text:
                    chunk = sc.output_transcription.text.strip()
                    if chunk:
                        transcript.append(chunk)

                if sc.turn_complete:
                    if transcript and self._player:
                        full = re.sub(r"\s+", " ", " ".join(transcript)).strip()
                        if full:
                            self._player.write_log(f"MJ: {full}")
                            print(f"[Vision] 💬 {full}")
                    transcript = []
                    # Auto-close camera ~2s after MJ finishes speaking
                    if self._player and hasattr(self._player, "stop_camera_stream"):
                        async def _deferred_close():
                            await asyncio.sleep(2.0)
                            try:
                                self._player.stop_camera_stream()
                            except Exception:
                                pass
                        asyncio.create_task(_deferred_close())

        except Exception as e:
            print(f"[Vision] ⚠️  Recv error: {e}")
            raise  

    async def _play_loop(self) -> None:
        stream = sd.RawOutputStream(
            samplerate=_RECEIVE_SAMPLE_RATE,
            channels=_CHANNELS,
            dtype="int16",
            blocksize=_CHUNK_SIZE,
        )
        stream.start()
        try:
            while True:
                chunk = await self._audio_in.get()
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[Vision] ❌ Play error: {e}")
            raise
        finally:
            stream.stop()
            stream.close()

_session      = _VisionSession()
_session_lock = threading.Lock()
_session_up   = False


def _ensure_session(player=None) -> None:
    global _session_up
    with _session_lock:
        if not _session_up:
            _session.start(player=player)
            _session_up = True
        elif player is not None:
            _session._player = player


def screen_process(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> bool:

    params    = parameters or {}
    user_text = (params.get("text") or params.get("user_text") or "").strip()
    angle     = params.get("angle", "screen").lower().strip()

    if not user_text:
        print("[Vision] ⚠️  No question provided — aborting")
        return False

    print(f"[Vision] ▶ angle={angle!r}  question='{user_text[:80]}'")

    try:
        _ensure_session(player=player)
    except Exception as e:
        print(f"[Vision] ❌ Could not start session: {e}")
        return False

    try:
        if angle == "camera":
            image_bytes, mime_type = _capture_camera()
            saved_path = _save_camera_capture(image_bytes)
            print(f"[Vision] 📷 Camera: {len(image_bytes):,} bytes saved to {saved_path}")
            if player and hasattr(player, "show_camera_frame"):
                try:
                    player.show_camera_frame(image_bytes)
                except Exception as _e:
                    print(f"[Vision] ⚠️  Camera preview failed: {_e}")
            if player and hasattr(player, "start_camera_stream"):
                try:
                    player.start_camera_stream()
                except Exception as _e:
                    print(f"[Vision] ⚠️  Camera stream failed: {_e}")
        else:
            image_bytes, mime_type = _capture_screen()
            print(f"[Vision] 🖥️  Screen: {len(image_bytes):,} bytes")
    except Exception as e:
        print(f"[Vision] ❌ Capture error: {e}")
        return False

    _session.analyze(image_bytes, mime_type, user_text)
    return True


def warmup_session(player=None) -> None:
    try:
        _ensure_session(player=player)
    except Exception as e:
        print(f"[Vision] ⚠️  Warmup failed: {e}")

if __name__ == "__main__":
    print("[TEST] screen_processor.py")
    print("=" * 52)
    mode = input("angle — screen / camera (default: screen): ").strip().lower() or "screen"
    q    = input("Question (Enter = default): ").strip() or "What do you see? Be brief."

    t0 = time.perf_counter()
    warmup_session()
    print(f"Session ready in {time.perf_counter()-t0:.2f}s\n")

    t1 = time.perf_counter()
    ok = screen_process({"angle": mode, "text": q})
    print(f"Queued in {time.perf_counter()-t1:.3f}s — waiting for audio...")
    time.sleep(10)
    print("Done." if ok else "Failed.")
