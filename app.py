
import os
import json
import uuid
import itertools
import math
from pathlib import Path
from datetime import datetime, timezone

import cv2
import numpy as np

from flask import (
    Flask, render_template, request,
    send_from_directory, jsonify, url_for
)

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
DATA_FILE = BASE_DIR / "data" / "constellations.json"

UPLOAD_FOLDER.mkdir(exist_ok=True)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_CANDIDATES = 20
MATCH_THRESHOLD = 0.12

with open(DATA_FILE, "r", encoding="utf-8") as f:
    constellation_data = json.load(f)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def detect_stars(image):
    if image is None or image.size == 0:
        raise ValueError("Invalid image")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    _, threshold = cv2.threshold(
        blurred, 165, 255, cv2.THRESH_BINARY
    )

    contours, _ = cv2.findContours(
        threshold,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    detected_stars = []

    for contour in contours:
        area = cv2.contourArea(contour)

        if 1 <= area <= 100:
            moments = cv2.moments(contour)

            if moments["m00"] == 0:
                continue

            x = int(moments["m10"] / moments["m00"])
            y = int(moments["m01"] / moments["m00"])

            brightness = float(gray[y, x])

            detected_stars.append({
                "x": x,
                "y": y,
                "brightness": brightness
            })

    # Keep the strongest candidates when there are many detections.
    detected_stars.sort(
        key=lambda star: star["brightness"],
        reverse=True
    )

    detected_stars = detected_stars[:MAX_CANDIDATES]

    for star in detected_stars:
        cv2.circle(
            image,
            (star["x"], star["y"]),
            5,
            (80, 255, 160),
            1
        )

    return image, detected_stars


def normalize_stars(stars, width, height):
    # Preserve aspect ratio rather than stretching the image
    # into a square.
    scale = max(width, height)

    return np.array([
        [
            (star["x"] - width / 2) / scale,
            (star["y"] - height / 2) / scale
        ]
        for star in stars
    ], dtype=float)


def distance_signature(points):
    distances = []

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            distances.append(
                np.linalg.norm(points[i] - points[j])
            )

    distances = np.sort(np.array(distances))

    if len(distances) == 0 or distances[-1] < 1e-9:
        return None

    return distances / distances[-1]


def match_constellation(stars, data):
    if len(stars) < 3:
        return None, None

    best_match = None
    best_score = float("inf")

    for constellation in data["constellations"]:
        pattern = np.array(
            constellation["stars"],
            dtype=float
        )

        required = len(pattern)

        if len(stars) < required:
            continue

        pattern_signature = distance_signature(pattern)

        if pattern_signature is None:
            continue

        # Test subsets rather than assuming every detected
        # bright object belongs to the constellation.
        for subset in itertools.combinations(
            range(len(stars)), required
        ):
            candidate = stars[list(subset)]

            signature = distance_signature(candidate)

            if signature is None:
                continue

            score = float(np.mean(
                np.abs(signature - pattern_signature)
            ))

            if score < best_score:
                best_score = score
                best_match = constellation

    if best_match is None or best_score > MATCH_THRESHOLD:
        return None, None

    confidence = max(
        0.0,
        min(100.0, (1.0 - best_score / MATCH_THRESHOLD) * 100)
    )

    return best_match, round(confidence, 1)


def process_image(file):
    if not file or not file.filename:
        raise ValueError("Please select an image.")

    if not allowed_file(file.filename):
        raise ValueError("Please upload a JPG, PNG or WEBP image.")

    image_bytes = file.read()

    if not image_bytes:
        raise ValueError("The uploaded image is empty.")

    image_array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("The uploaded file is not a valid image.")

    if image.shape[0] < 50 or image.shape[1] < 50:
        raise ValueError("The image is too small to analyze.")

    result, stars = detect_stars(image.copy())

    height, width = result.shape[:2]

    normalized = normalize_stars(stars, width, height)

    constellation, confidence = match_constellation(
        normalized,
        constellation_data
    )

    output_filename = f"result_{uuid.uuid4().hex}.jpg"
    output_path = UPLOAD_FOLDER / output_filename

    success = cv2.imwrite(str(output_path), result)

    if not success:
        raise ValueError("Unable to save the processed image.")

    return {
        "result_image": output_filename,
        "star_count": len(stars),
        "constellation": constellation,
        "confidence": confidence
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        result = process_image(request.files.get("image"))

        return render_template(
            "index.html",
            **result,
            error=None
        )

    except ValueError as e:
        return render_template(
            "index.html",
            error=str(e)
        ), 400

    except Exception:
        app.logger.exception("Image processing failed")
        return render_template(
            "index.html",
            error="Something went wrong while analyzing the image."
        ), 500


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """JSON API used by the Android and iOS applications."""

    try:
        result = process_image(request.files.get("image"))

        constellation = result["constellation"]

        return jsonify({
            "success": True,
            "result_image": url_for(
                "uploaded_file",
                filename=result["result_image"],
                _external=True
            ),
            "star_count": result["star_count"],
            "confidence": result["confidence"],
            "constellation": constellation
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception:
        app.logger.exception("API processing failed")
        return jsonify({
            "success": False,
            "error": "Image processing failed."
        }), 500


@app.route("/api/constellations")
def api_constellations():
    return jsonify(constellation_data)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    if not filename.startswith("result_"):
        return "Not found", 404

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


@app.errorhandler(413)
def file_too_large(error):
    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "error": "Image must be smaller than 12 MB."
        }), 413

    return render_template(
        "index.html",
        error="Image must be smaller than 12 MB."
    ), 413


@app.route("/api/location", methods=["POST"])
def receive_location():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "Invalid location data."
        }), 400

    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data["accuracy"])

    except (KeyError, TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "Missing or invalid coordinates."
        }), 400

   

    if not all(map(math.isfinite, [
        latitude, longitude, accuracy
    ])):
        return jsonify({
            "success": False,
            "error": "Coordinates must be finite numbers."
        }), 400

    if not -90 <= latitude <= 90:
        return jsonify({
            "success": False,
            "error": "Invalid latitude."
        }), 400

    if not -180 <= longitude <= 180:
        return jsonify({
            "success": False,
            "error": "Invalid longitude."
        }), 400

    if not 0 <= accuracy <= 1000000:
        return jsonify({
            "success": False,
            "error": "Invalid location accuracy."
        }), 400

    return jsonify({
        "success": True,
        "message": "Location received successfully.",
        "latitude": latitude,
        "longitude": longitude,
        "accuracy": accuracy
    })



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

# =========================================
# LOCATION-BASED CONSTELLATION VISIBILITY
# =========================================

SKY_CATALOG_FILE = BASE_DIR / "data" / "sky_catalog.json"

with open(SKY_CATALOG_FILE, "r", encoding="utf-8") as f:
    sky_catalog = json.load(f)


def julian_date(dt):
    """Convert UTC datetime to Julian Date."""

    dt = dt.astimezone(timezone.utc)

    year = dt.year
    month = dt.month

    day = (
        dt.day
        + dt.hour / 24
        + dt.minute / 1440
        + dt.second / 86400
        + dt.microsecond / 86400000000
    )

    if month <= 2:
        year -= 1
        month += 12

    A = math.floor(year / 100)
    B = 2 - A + math.floor(A / 4)

    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day + B - 1524.5
    )


def local_sidereal_time(dt, longitude):
    """Calculate local mean sidereal time in degrees."""

    jd = julian_date(dt)
    T = (jd - 2451545.0) / 36525.0

    gmst = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * T**2
        - T**3 / 38710000
    )

    return (gmst + longitude) % 360


def calculate_altitude_azimuth(ra_hours, dec_degrees,
                               latitude, longitude, dt):
    """Convert RA/Dec to local altitude and azimuth."""

    lst = local_sidereal_time(dt, longitude)

    ra_degrees = ra_hours * 15

    hour_angle = (lst - ra_degrees + 180) % 360 - 180

    H = math.radians(hour_angle)
    dec = math.radians(dec_degrees)
    lat = math.radians(latitude)

    sin_alt = (
        math.sin(lat) * math.sin(dec)
        + math.cos(lat) * math.cos(dec) * math.cos(H)
    )

    altitude = math.degrees(
        math.asin(max(-1, min(1, sin_alt)))
    )

    y = -math.sin(H) * math.cos(dec)

    x = (
        math.sin(dec) * math.cos(lat)
        - math.cos(dec) * math.sin(lat) * math.cos(H)
    )

    azimuth = math.degrees(math.atan2(y, x))
    azimuth = (azimuth + 360) % 360

    return round(altitude, 2), round(azimuth, 2)


def get_direction(azimuth):

    directions = [
        "North",
        "North-East",
        "East",
        "South-East",
        "South",
        "South-West",
        "West",
        "North-West"
    ]

    index = round(azimuth / 45) % 8

    return directions[index]


def find_visible_constellations(latitude, longitude, dt):
    """Find constellations with representative stars above 10 degrees."""

    results = []

    for constellation in sky_catalog["constellations"]:

        visible_stars = []
        all_stars = []

        for star in constellation["stars"]:

            altitude, azimuth = calculate_altitude_azimuth(
                star["ra"],
                star["dec"],
                latitude,
                longitude,
                dt
            )

            star_info = {
                "name": star["name"],
                "altitude": altitude,
                "azimuth": azimuth,
                "direction": get_direction(azimuth)
            }

            all_stars.append(star_info)

            if altitude > 10:
                visible_stars.append(star_info)

        if visible_stars:

            highest_star = max(
                visible_stars,
                key=lambda star: star["altitude"]
            )

            results.append({
                "name": constellation["name"],
                "visible_star_count": len(visible_stars),
                "total_star_count": len(all_stars),
                "highest_altitude": highest_star["altitude"],
                "direction": highest_star["direction"],
                "azimuth": highest_star["azimuth"],
                "stars": visible_stars
            })

    results.sort(
        key=lambda item: item["highest_altitude"],
        reverse=True
    )

    return results
