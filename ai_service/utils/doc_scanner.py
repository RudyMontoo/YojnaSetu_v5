"""
doc_scanner.py — OpenCV Document Preprocessing Pipeline
Yojna Setu Jan-Sahayak Lens

All operations work on in-memory numpy arrays.
NO files are written to disk at any point.
"""
import io
import numpy as np
import cv2
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    Full OpenCV preprocessing pipeline.
    Input:  raw image bytes (JPEG / PNG / WEBP)
    Output: cleaned, thresholded numpy array ready for OCR
    Raises: ValueError on corrupt or unreadable input
    """
    # --- Decode bytes → numpy (no disk write) ---
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Image could not be decoded. Please use JPEG, PNG, or WEBP.")

    # --- Resize if too large (OCR works best at ~2x document size) ---
    h, w = img.shape[:2]
    max_dim = 2048
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # --- Deskew before graying ---
    img = deskew(img)

    # --- Document contour + perspective correction ---
    warped = detect_document_contour(img)
    if warped is not None:
        img = warped

    # --- Convert to grayscale ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- Bilateral filter: removes noise while preserving edges (character strokes) ---
    denoised = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # --- Adaptive thresholding: handles uneven lighting (common in phone photos) ---
    thresh = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11, C=2
    )

    # --- Morphological cleanup: close small gaps in characters ---
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    return cleaned


def detect_document_contour(img: np.ndarray) -> Optional[np.ndarray]:
    """
    Detects the 4-corner contour of a document and applies perspective transform.
    Returns the perspective-corrected image, or None if no clear contour found.
    """
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)

        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        # Find largest contour (likely the document)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        doc_contour = None
        for c in contours[:5]:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                doc_contour = approx
                break

        if doc_contour is None:
            return None

        # Perspective warp
        pts = doc_contour.reshape(4, 2).astype(np.float32)
        pts = _order_points(pts)

        widthA  = np.linalg.norm(pts[2] - pts[3])
        widthB  = np.linalg.norm(pts[1] - pts[0])
        heightA = np.linalg.norm(pts[1] - pts[2])
        heightB = np.linalg.norm(pts[0] - pts[3])
        maxW = max(int(widthA), int(widthB))
        maxH = max(int(heightA), int(heightB))

        if maxW < 100 or maxH < 100:
            return None  # contour too small — false positive

        dst = np.array([[0, 0], [maxW - 1, 0], [maxW - 1, maxH - 1], [0, maxH - 1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(pts, dst)
        warped = cv2.warpPerspective(img, M, (maxW, maxH))
        return warped

    except Exception as e:
        logger.warning(f"Contour detection failed (non-fatal): {e}")
        return None


def deskew(img: np.ndarray) -> np.ndarray:
    """
    Detects and corrects rotation of a document image.
    Uses Hough line detection to find the dominant angle.
    """
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
        if lines is None:
            return img

        angles = []
        for line in lines[:20]:  # sample top 20 lines
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:
                angles.append(angle)

        if not angles:
            return img

        median_angle = np.median(angles)
        if abs(median_angle) < 0.5:  # already straight
            return img

        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        return rotated

    except Exception as e:
        logger.warning(f"Deskew failed (non-fatal): {e}")
        return img


def pdf_page_to_image_bytes(pdf_bytes: bytes, page_num: int = 0) -> list[bytes]:
    """
    Convert PDF pages to image bytes using pdf2image.
    Returns list of JPEG image bytes, one per page.
    Raises: ImportError if pdf2image/poppler not installed
            ValueError for corrupt PDF
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        raise ImportError(
            "pdf2image not installed. Run: pip install pdf2image\n"
            "Also requires poppler: sudo apt install poppler-utils"
        )

    try:
        pages = convert_from_bytes(pdf_bytes, dpi=200, fmt="jpeg")
        result = []
        for page in pages:
            buf = io.BytesIO()
            page.save(buf, format="JPEG", quality=90)
            result.append(buf.getvalue())
        return result
    except Exception as e:
        raise ValueError(f"Could not process PDF: {e}")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left: smallest sum
    rect[2] = pts[np.argmax(s)]   # bottom-right: largest sum
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right: smallest diff
    rect[3] = pts[np.argmax(diff)]  # bottom-left: largest diff
    return rect
