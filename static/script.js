
const input = document.getElementById("image-input");
const dropZone = document.getElementById("drop-zone");
const preview = document.getElementById("preview");
const fileInfo = document.getElementById("file-info");
const form = document.getElementById("upload-form");

function displayFile(file) {
    if (!file) return;

    const allowed = ["image/jpeg", "image/png", "image/webp"];

    if (!allowed.includes(file.type)) {
        fileInfo.textContent = "Please select a JPG, PNG or WEBP image.";
        input.value = "";
        preview.style.display = "none";
        return;
    }

    if (file.size > 12 * 1024 * 1024) {
        fileInfo.textContent = "Your image must be smaller than 12 MB.";
        input.value = "";
        preview.style.display = "none";
        return;
    }

    preview.src = URL.createObjectURL(file);
    preview.style.display = "block";

    fileInfo.textContent =
        `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
}

input.addEventListener("change", () => {
    displayFile(input.files[0]);
});

dropZone.addEventListener("dragover", event => {
    event.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", event => {
    event.preventDefault();
    dropZone.classList.remove("dragover");

    const file = event.dataTransfer.files[0];

    if (!file) return;

    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;

    displayFile(file);
});

form.addEventListener("submit", event => {
    if (!input.files.length) {
        event.preventDefault();
        fileInfo.textContent = "Please select an image first.";
        return;
    }

    const button = form.querySelector("button");
    button.disabled = true;
    button.innerHTML = "✧ Analyzing your sky...";
});

const results = document.getElementById("results");

if (results) {
    results.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
}

// ======================================
// BROWSER GEOLOCATION
// ======================================

const locationButton = document.getElementById("location-button");
const locationStatus = document.getElementById("location-status");
const locationDetails = document.getElementById("location-details");

const latitudeElement = document.getElementById("latitude");
const longitudeElement = document.getElementById("longitude");
const accuracyElement = document.getElementById("accuracy");

const clearLocationButton = document.getElementById("clear-location");

let selectedLocation = null;

if (locationButton) {

    locationButton.addEventListener("click", () => {

        if (!("geolocation" in navigator)) {
            locationStatus.textContent =
                "Geolocation is not supported by your browser.";
            return;
        }

        locationButton.disabled = true;
        locationButton.textContent = "Finding your location...";

        locationStatus.textContent =
            "Please allow location access in your browser.";

        navigator.geolocation.getCurrentPosition(

            async (position) => {

                const latitude = position.coords.latitude;
                const longitude = position.coords.longitude;
                const accuracy = position.coords.accuracy;

                selectedLocation = {
                    latitude,
                    longitude,
                    accuracy
                };

                latitudeElement.textContent =
                    latitude.toFixed(5) + "°";

                longitudeElement.textContent =
                    longitude.toFixed(5) + "°";

                accuracyElement.textContent =
                    Math.round(accuracy) + " m";

                locationDetails.hidden = false;

                locationStatus.textContent =
                    "Your location was detected successfully.";

                locationButton.disabled = false;
                locationButton.textContent =
                    "✦ Refresh my location";

                // Send coordinates to Flask
                try {

                    const response = await fetch("/api/location", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify(selectedLocation)
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(
                            data.error || "Unable to save location."
                        );
                    }

                    locationStatus.textContent =
                        "Location received successfully.";
                    // Calculate visible constellations
                         await loadVisibleConstellations(
                         latitude,
                         longitude
                    );

                } catch (error) {

                    locationStatus.textContent =
                        "Location detected, but could not reach the server.";

                    console.error(error);
                }
            },

            (error) => {

                const messages = {
                    1: "Location permission was denied. Please enable it in browser settings.",
                    2: "Your location is currently unavailable.",
                    3: "Location request timed out. Please try again."
                };

                locationStatus.textContent =
                    messages[error.code] ||
                    "Unable to detect your location.";

                locationButton.disabled = false;
                locationButton.textContent =
                    "✦ Try again";
            },

            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 60000
            }
        );
    });
}

// Clear selected location
if (clearLocationButton) {

    clearLocationButton.addEventListener("click", () => {

        selectedLocation = null;

        locationDetails.hidden = true;

       const visibilityResults =
              document.getElementById("visibility-results");

       if (visibilityResults) {
              visibilityResults.hidden = true;
}

        latitudeElement.textContent = "—";
        longitudeElement.textContent = "—";
        accuracyElement.textContent = "—";

        locationStatus.textContent =
            "Your location has been cleared.";

        locationButton.textContent =
            "✦ Use my current location";
    });
}

// ======================================
// VISIBLE CONSTELLATIONS API
// ======================================

async function loadVisibleConstellations(latitude, longitude) {

    const visibilityResults =
        document.getElementById("visibility-results");

    const visibilityStatus =
        document.getElementById("visibility-status");

    const visibilityTime =
        document.getElementById("visibility-time");

    const constellationList =
        document.getElementById("visible-constellation-list");

   if (
    !visibilityResults ||
    !visibilityStatus ||
    !visibilityTime ||
    !constellationList
   ) {
    console.error("Visibility HTML elements are missing.");
    return;
   }

    visibilityResults.hidden = false;

    visibilityStatus.textContent =
        "Calculating your visible constellations...";

    constellationList.replaceChildren();

    try {

        const response = await fetch(
            "/api/visible-constellations",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    latitude: latitude,
                    longitude: longitude,
                    observed_at: new Date().toISOString()
                })
            }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(
                data.error || "Unable to calculate visibility."
            );
        }

        visibilityTime.textContent =
            "Observation time: " +
            new Date(data.observed_at).toLocaleString();

        if (data.constellations.length === 0) {

            visibilityStatus.textContent =
                "No representative constellation stars are above 10° altitude.";

            return;
        }

        visibilityStatus.textContent =
            data.visible_count +
            " constellations found above the horizon.";

        data.constellations.forEach(constellation => {

            const card = document.createElement("article");
            card.className = "visible-constellation-card";

            const heading = document.createElement("h4");
            heading.textContent = constellation.name;

            const details = document.createElement("p");

            details.textContent =
                constellation.visible_star_count +
                " of " +
                constellation.total_star_count +
                " representative stars visible";

            const direction = document.createElement("p");

            direction.textContent =
                "Direction: " + constellation.direction;

            const altitude = document.createElement("p");

            altitude.textContent =
                "Highest star altitude: " +
                constellation.highest_altitude + "°";

            card.append(
                heading,
                details,
                direction,
                altitude
            );

            constellationList.appendChild(card);

        });

    } catch (error) {

        visibilityStatus.textContent =
            "Could not calculate visible constellations. Please try again.";

        console.error("Visibility API error:", error);
    }
}


