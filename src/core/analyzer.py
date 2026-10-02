"""Preview image sharpness scoring and perceptual hashing."""

from pathlib import Path

import cv2
import imagehash
from PIL import Image


def calculate_sharpness(image_path: Path) -> float:
    """Return Laplacian variance, or zero for an unreadable image."""
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return 0.0
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def compute_phash(image_path: Path) -> imagehash.ImageHash:
    """Compute the preview's perceptual hash and release the image file."""
    with Image.open(image_path) as image:
        return imagehash.phash(image)
