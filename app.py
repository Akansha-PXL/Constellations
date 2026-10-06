from flask import Flask, render_template, request, send_from_directory
import cv2
import numpy as np
import os
import uuid
import json

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

DATA_FILE = "data/constellations.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    constellation_data = json.load(f)


def detect_stars(image_path):
    image = cv2.imread(image_path)

    if image is None:
        raise ValueError("Unable to read image")

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Detect bright objects
    _, threshold = cv2.threshold(
        blurred,
        150,
        255,
        cv2.THRESH_BINARY
    )

    # Find bright regions
    contours, _ = cv2.findContours(
        threshold,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    detected_stars = []

    for contour in contours:
        area = cv2.contourArea(contour)

        # Ignore extremely small/noisy regions
        if 1 <= area <= 100:
            moments = cv2.moments(contour)

            if moments["m00"] != 0:
                x = int(moments["m10"] / moments["m00"])
                y = int(moments["m01"] / moments["m00"])

                detected_stars.append((x, y))

                cv2.circle(
                    image,
                    (x, y),
                    5,
                    (0, 255, 0),
                    1
                )

    return image, detected_stars


def normalize_stars(stars, image_width, image_height):
    normalized = []

    for x, y in stars:
        normalized_x = x / image_width
        normalized_y = y / image_height

        normalized.append(
            (normalized_x, normalized_y)
        )

    return normalized


def match_constellation(stars, constellation_data):
    if len(stars) < 3:
        return None

    detected = np.array(stars, dtype=float)

    best_match = None
    best_score = float("inf")

    for constellation in constellation_data["constellations"]:

        pattern = np.array(
            constellation["stars"],
            dtype=float
        )

        if len(detected) < len(pattern):
            continue

        # Calculate pairwise distances for the detected stars
        detected_distances = []

        for i in range(len(detected)):
            for j in range(i + 1, len(detected)):
                distance = np.linalg.norm(
                    detected[i] - detected[j]
                )
                detected_distances.append(distance)

        # Calculate pairwise distances for the constellation pattern
        pattern_distances = []

        for i in range(len(pattern)):
            for j in range(i + 1, len(pattern)):
                distance = np.linalg.norm(
                    pattern[i] - pattern[j]
                )
                pattern_distances.append(distance)

        # Sort distances so that the comparison is
        # independent of the order of the stars
        detected_distances.sort()
        pattern_distances.sort()

        # Only compare the number of distances
        # that the constellation pattern requires
        detected_distances = detected_distances[
            :len(pattern_distances)
        ]

        # Normalize distances by the largest distance
        if detected_distances[-1] == 0:
            continue

        detected_distances = np.array(
            detected_distances
        ) / detected_distances[-1]

        pattern_distances = np.array(
            pattern_distances
        ) / pattern_distances[-1]

        # Calculate difference between the patterns
        score = np.mean(
            np.abs(
                detected_distances - pattern_distances
            )
        )

        if score < best_score:
            best_score = score
            best_match = constellation

    return best_match


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():

    if "image" not in request.files:
        return "No image uploaded", 400

    file = request.files["image"]

    if file.filename == "":
        return "No image selected", 400

    filename = str(uuid.uuid4()) + ".jpg"

    input_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(input_path)

    try:
        result, stars = detect_stars(input_path)

        height, width = result.shape[:2]

        normalized_stars = normalize_stars(
            stars,
            width,
            height
        )

        constellation = match_constellation(
            normalized_stars,
            constellation_data
        )

        output_filename = "result_" + filename

        output_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            output_filename
        )

        cv2.imwrite(output_path, result)

        return render_template(
            "index.html",
            result_image=output_filename,
            star_count=len(stars),
            constellation=constellation
        )

    except Exception as e:
        return f"Processing error: {e}", 500


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )


if __name__ == "__main__":
    app.run(debug=True)
