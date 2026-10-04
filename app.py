from flask import Flask, render_template, request, send_from_directory
import cv2
import numpy as np
import os
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def detect_stars(image_path):
    """
    Detect stars in a night-sky image.

    Uses:
    - Contrast enhancement
    - Background estimation
    - Difference image
    - Multiple brightness thresholds
    - Connected-component detection
    - Blob detection
    - Size/shape filtering
    - Non-maximum suppression
    """

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError("Unable to read image.")

    original = image.copy()

    

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

   

    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8)
    )

    enhanced = clahe.apply(gray)

    

    blurred = cv2.GaussianBlur(
        enhanced,
        (3, 3),
        0
    )

    

    background = cv2.GaussianBlur(
        blurred,
        (0, 0),
        sigmaX=15
    )

   
    difference = cv2.subtract(
        blurred,
        background
    )

    

    difference = cv2.normalize(
        difference,
        None,
        0,
        255,
        cv2.NORM_MINMAX
    )

    

    threshold_values = [
        12,
        18,
        25,
        35,
        50
    ]

    candidate_points = []

    height, width = gray.shape

    for threshold_value in threshold_values:

        _, binary = cv2.threshold(
            difference,
            threshold_value,
            255,
            cv2.THRESH_BINARY
        )

        
        binary = cv2.morphologyEx(
            binary,
            cv2.MORPH_OPEN,
            np.ones((2, 2), np.uint8)
        )

        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:

            area = cv2.contourArea(contour)

            
            if area < 0.5 or area > 80:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # Reject huge objects.
            if w > 18 or h > 18:
                continue

            # Reject objects touching image edges.
            if x <= 1 or y <= 1:
                continue

            if x + w >= width - 1:
                continue

            if y + h >= height - 1:
                continue

          

            moments = cv2.moments(contour)

            if moments["m00"] == 0:
                continue

            cx = int(
                moments["m10"] /
                moments["m00"]
            )

            cy = int(
                moments["m01"] /
                moments["m00"]
            )

            

            radius = 4

            x1 = max(0, cx - radius)
            x2 = min(width, cx + radius + 1)

            y1 = max(0, cy - radius)
            y2 = min(height, cy + radius + 1)

            region = gray[y1:y2, x1:x2]

            if region.size == 0:
                continue

            brightness = float(
                np.mean(region)
            )

            maximum_brightness = float(
                np.max(region)
            )

            

            if maximum_brightness < 35:
                continue

            

            aspect_ratio = w / max(h, 1)

            if aspect_ratio > 4 or aspect_ratio < 0.25:
                continue

            
            candidate_points.append(
                (
                    cx,
                    cy,
                    brightness,
                    maximum_brightness,
                    area
                )
            )

  

    params = cv2.SimpleBlobDetector_Params()

    params.minThreshold = 5
    params.maxThreshold = 255
    params.thresholdStep = 10

    params.filterByArea = True
    params.minArea = 1
    params.maxArea = 100

    params.filterByCircularity = True
    params.minCircularity = 0.15

    params.filterByConvexity = False
    params.filterByInertia = False

    detector = cv2.SimpleBlobDetector_create(
        params
    )

    keypoints = detector.detect(
        blurred
    )

    for keypoint in keypoints:

        cx = int(keypoint.pt[0])
        cy = int(keypoint.pt[1])

        if cx <= 1 or cy <= 1:
            continue

        if cx >= width - 1 or cy >= height - 1:
            continue

        x1 = max(0, cx - 4)
        x2 = min(width, cx + 5)

        y1 = max(0, cy - 4)
        y2 = min(height, cy + 5)

        region = gray[y1:y2, x1:x2]

        if region.size == 0:
            continue

        brightness = float(
            np.mean(region)
        )

        maximum_brightness = float(
            np.max(region)
        )

        if maximum_brightness < 30:
            continue

        candidate_points.append(
            (
                cx,
                cy,
                brightness,
                maximum_brightness,
                1
            )
        )

   

    candidate_points.sort(
        key=lambda p: p[3],
        reverse=True
    )

    final_points = []

    minimum_distance = 5

    for candidate in candidate_points:

        cx, cy = candidate[0], candidate[1]

        too_close = False

        for existing in final_points:

            ex, ey = existing[0], existing[1]

            distance = np.sqrt(
                (cx - ex) ** 2 +
                (cy - ey) ** 2
            )

            if distance < minimum_distance:

                too_close = True
                break

        if not too_close:
            final_points.append(
                candidate
            )

   

    maximum_stars = 1000

    final_points.sort(
        key=lambda p: p[3],
        reverse=True
    )

    final_points = final_points[
        :maximum_stars
    ]

    

    result = original.copy()

    for index, point in enumerate(final_points):

        cx = int(point[0])
        cy = int(point[1])

        brightness = point[3]

        
        if brightness > 180:
            radius = 7
            color = (0, 255, 255)

        elif brightness > 120:
            radius = 6
            color = (0, 255, 0)

        elif brightness > 80:
            radius = 5
            color = (255, 100, 0)

        else:
            radius = 4
            color = (255, 0, 255)

        cv2.circle(
            result,
            (cx, cy),
            radius,
            color,
            1
        )

        # Optional star number
        cv2.putText(
            result,
            str(index + 1),
            (cx + 5, cy - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            color,
            1,
            cv2.LINE_AA
        )

    return result, final_points




@app.route("/")
def index():

    return render_template(
        "index.html"
    )




@app.route(
    "/analyze",
    methods=["POST"]
)
def analyze():

    if "image" not in request.files:

        return "No image uploaded.", 400

    file = request.files["image"]

    if file.filename == "":

        return "No image selected.", 400

   
    filename = (
        str(uuid.uuid4()) +
        ".jpg"
    )

    input_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(
        input_path
    )

    try:

        
        result, stars = detect_stars(
            input_path
        )

        

        output_filename = (
            "result_" +
            filename
        )

        output_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            output_filename
        )

        cv2.imwrite(
            output_path,
            result
        )

       
        return render_template(
            "index.html",
            result_image=output_filename,
            star_count=len(stars)
        )

    except Exception as error:

        return (
            f"Processing error: {error}",
            500
        )




@app.route(
    "/uploads/<filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )



if __name__ == "__main__":

    app.run(
        debug=True
    )
