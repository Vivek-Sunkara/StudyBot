import cv2
import numpy as np

def sample_video_frames(path, max_frames=4):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    indices = np.linspace(0, max(count - 1, 0), min(max_frames, max(count, 1))).astype(int)
    frames = []
    for index in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        if not ok:
            continue
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            frames.append((int(index), encoded.tobytes()))
    cap.release()
    return frames

def analyze_video_file(path, max_frames=24):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Video could not be opened")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = count / fps if fps else 0
    indices = np.linspace(0, max(count-1, 0), min(max_frames, max(count, 1))).astype(int)
    result = []
    previous = None
    for index in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (160, 90))
        edges = cv2.Canny(gray, 80, 160)
        change = None if previous is None else float(np.mean(cv2.absdiff(small, previous)))
        previous = small
        result.append({
            "frame": int(index),
            "timestamp": round(index / fps, 3) if fps else 0,
            "brightness": round(float(gray.mean()), 2),
            "edge_density": round(float(np.count_nonzero(edges)/edges.size), 5),
            "scene_change": round(change, 2) if change is not None else None
        })
    cap.release()
    return {
        "fps": round(fps, 3), "frame_count": count, "duration_seconds": round(duration, 3),
        "width": width, "height": height, "sampled_frames": result,
        "note": "Deterministic frame/scene analysis only; no speech recognition or pretrained vision model is used."
    }
