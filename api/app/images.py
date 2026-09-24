import io
import cv2
import numpy as np
from PIL import Image

def analyze_image_bytes(data):
    image = Image.open(io.BytesIO(data))
    image.load()
    rgb = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    density = float(np.count_nonzero(edges) / edges.size)
    brightness = float(gray.mean())
    return {
        "width": image.width,
        "height": image.height,
        "brightness": round(brightness, 2),
        "contrast_std": round(float(gray.std()), 2),
        "sharpness_score": round(blur, 2),
        "edge_density": round(density, 5),
        "significant_contours": sum(cv2.contourArea(c) >= max(20, gray.size*0.00005) for c in contours),
        "assessment": {
            "brightness": "dark" if brightness < 70 else "bright" if brightness > 190 else "moderate",
            "sharpness": "low" if blur < 80 else "moderate" if blur < 300 else "high",
            "edge_density": "low" if density < .03 else "moderate" if density < .12 else "high"
        },
        "note": "Deterministic OpenCV analysis only; no OCR or pretrained vision model is used."
    }
