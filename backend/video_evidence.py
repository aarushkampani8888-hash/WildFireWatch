"""Bounded frame extraction for user-uploaded video evidence."""
import base64
import hashlib
import os
import tempfile

MAX_VIDEO_BYTES = 25 * 1024 * 1024
MAX_DURATION_SECONDS = 90
FRAME_SAMPLES = 6
MAX_FRAME_WIDTH = 1024
MIME_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}


def extract_frames(raw: bytes, content_type: str):
    if len(raw) > MAX_VIDEO_BYTES:
        raise ValueError("Video exceeds the 25 MB upload limit.")
    extension = MIME_EXTENSIONS.get(content_type.lower().split(";", 1)[0].strip())
    if not extension:
        raise ValueError("Use an MP4, WebM, or QuickTime video.")
    try:
        import cv2
    except ImportError:
        raise RuntimeError("Video decoding is unavailable; install the inference requirements.") from None

    path = None
    capture = None
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temporary:
            temporary.write(raw)
            path = temporary.name
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            raise ValueError("This video could not be decoded. Try MP4 (H.264) or WebM.")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if source_width * source_height > 40_000_000:
            raise ValueError("Video frame resolution exceeds the analysis limit.")
        duration = count / fps if fps > 0 and count > 0 else 0
        if not duration:
            raise ValueError("Video duration could not be read.")
        if duration > MAX_DURATION_SECONDS:
            raise ValueError("Video is longer than the 90-second analysis limit.")

        frames, seen = [], set()
        for index in range(FRAME_SAMPLES):
            last_offset = max(0, duration - 0.001)
            offset = max(0, min(last_offset, duration * (index + 0.5) / FRAME_SAMPLES))
            capture.set(cv2.CAP_PROP_POS_MSEC, offset * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            if not width or not height:
                continue
            if width * height > 40_000_000:
                raise ValueError("Video frame resolution exceeds the analysis limit.")
            if width > MAX_FRAME_WIDTH:
                resized_height = round(height * MAX_FRAME_WIDTH / width)
                frame = cv2.resize(frame, (MAX_FRAME_WIDTH, resized_height), interpolation=cv2.INTER_AREA)
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
            if not ok:
                continue
            jpeg = encoded.tobytes()
            digest = hashlib.sha256(jpeg).digest()
            if digest in seen:
                continue
            seen.add(digest)
            frames.append({
                "offset_seconds": round(offset, 2),
                "image": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
            })
        if not frames:
            raise ValueError("No readable frames were found in this video.")
        return round(duration, 2), frames, extension
    finally:
        if capture is not None:
            capture.release()
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
