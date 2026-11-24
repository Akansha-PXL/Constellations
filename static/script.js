
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

