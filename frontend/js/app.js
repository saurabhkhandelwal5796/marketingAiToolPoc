const API_URL = "/generate";
const selectedFiles = [];
const MAX_TOTAL_FILES = 8;
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;

function setStatus(message, isError = false) {
    const status = document.getElementById('status-message');
    if (!status) return;

    if (!message) {
        status.style.display = 'none';
        status.className = 'status-message';
        status.innerText = '';
        return;
    }

    status.className = `status-message ${isError ? 'error' : 'success'}`;
    status.innerText = message;
    status.style.display = 'block';
}

function setLoading(isLoading) {
    const btn = document.getElementById('generateBtn');
    const btnText = document.getElementById('btnText');
    const loader = document.getElementById('loader');

    btn.disabled = isLoading;
    btnText.style.display = isLoading ? 'none' : 'block';
    loader.style.display = isLoading ? 'block' : 'none';
}

function formatContent(value, fallbackText) {
    if (value === null || value === undefined || value === "") {
        return fallbackText;
    }

    if (typeof value === "string") {
        return value;
    }

    if (typeof value === "object") {
        try {
            const orderedKeys = ["subject", "body", "message", "post", "title", "content"];
            const lines = [];

            orderedKeys.forEach((key) => {
                const raw = value[key];
                if (typeof raw === "string" && raw.trim()) {
                    if (key === "subject" || key === "title") {
                        lines.push(raw.trim());
                    } else {
                        lines.push(raw.trim());
                    }
                }
            });

            if (lines.length > 0) {
                return lines.join("\n\n");
            }

            const dynamicValues = Object.values(value)
                .filter((item) => typeof item === "string" && item.trim())
                .map((item) => item.trim());

            if (dynamicValues.length > 0) {
                return dynamicValues.join("\n\n");
            }

            return fallbackText;
        } catch (_) {
            return fallbackText;
        }
    }

    return String(value);
}

function updateUI(data) {
    document.getElementById('email-content').innerText =
        formatContent(data.email, "No email generated.");

    document.getElementById('whatsapp-content').innerText =
        formatContent(data.whatsapp, "No message generated.");

    document.getElementById('linkedin-content').innerText =
        formatContent(data.linkedin, "No post generated.");
}

function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderFileList() {
    const fileListEl = document.getElementById("file-list");
    if (!fileListEl) return;

    if (selectedFiles.length === 0) {
        fileListEl.innerHTML = "";
        return;
    }

    const escapeHtml = (value) => String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");

    fileListEl.innerHTML = selectedFiles
        .map((file, idx) => `
            <div class="file-chip">
                <span class="file-chip-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
                <span class="file-chip-size">${formatBytes(file.size)}</span>
                <button type="button" class="file-chip-remove" data-index="${idx}" aria-label="Remove file">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `)
        .join("");

    fileListEl.querySelectorAll(".file-chip-remove").forEach((btn) => {
        btn.addEventListener("click", () => {
            const idx = Number(btn.getAttribute("data-index"));
            if (!Number.isNaN(idx)) {
                selectedFiles.splice(idx, 1);
                renderFileList();
            }
        });
    });
}

function appendFiles(fileList) {
    const files = Array.from(fileList || []);
    const rejectedLarge = [];

    files.forEach((file) => {
        if (file.size > MAX_FILE_SIZE_BYTES) {
            rejectedLarge.push(file.name);
            return;
        }

        if (selectedFiles.length >= MAX_TOTAL_FILES) {
            return;
        }

        const key = `${file.name}-${file.size}-${file.lastModified}`;
        const alreadyAdded = selectedFiles.some(
            (existing) => `${existing.name}-${existing.size}-${existing.lastModified}` === key
        );
        if (!alreadyAdded) {
            selectedFiles.push(file);
        }
    });

    if (rejectedLarge.length > 0) {
        setStatus(`Skipped oversized files: ${rejectedLarge.join(", ")} (max 10MB each).`, true);
    } else if (selectedFiles.length >= MAX_TOTAL_FILES) {
        setStatus(`You can upload up to ${MAX_TOTAL_FILES} files.`, false);
    }

    renderFileList();
}

async function copyCardContent(targetId, button) {
    const source = document.getElementById(targetId);
    if (!source) return;

    const text = source.innerText.trim();
    if (!text) return;

    try {
        await navigator.clipboard.writeText(text);
        button.classList.add("copied");
        button.innerHTML = '<i class="fas fa-check"></i>';
        setStatus("Copied to clipboard.");
        setTimeout(() => {
            button.classList.remove("copied");
            button.innerHTML = '<i class="far fa-copy"></i>';
        }, 1400);
    } catch (error) {
        setStatus("Could not copy automatically. Please copy manually.", true);
    }
}

function initCopyActions() {
    const copyButtons = document.querySelectorAll(".copy-btn");
    copyButtons.forEach((button) => {
        const targetId = button.getAttribute("data-target");
        button.addEventListener("click", () => copyCardContent(targetId, button));
    });
}

function initUploader() {
    const dropzone = document.getElementById("upload-dropzone");
    const input = document.getElementById("supporting-file");
    if (!dropzone || !input) return;

    dropzone.addEventListener("click", () => input.click());
    input.addEventListener("change", (event) => {
        appendFiles(event.target.files);
        input.value = "";
    });

    dropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropzone.classList.remove("dragover");
        appendFiles(event.dataTransfer.files);
    });
}

async function generateMarketing() {
    const formData = new FormData();
    formData.append('company', document.getElementById('company').value);
    formData.append('campaign', document.getElementById('campaign').value);
    formData.append('description', document.getElementById('description').value);
    formData.append('website_url', document.getElementById('website-url').value);

    selectedFiles.forEach((file) => formData.append("files", file));

    try {
        setLoading(true);
        setStatus('');

        const response = await fetch(API_URL, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || "Could not generate content right now. Please try again.");
        }

        updateUI(data);
        setStatus('Campaign generated successfully.');

    } catch (error) {
        console.error(error);
        setStatus(error.message || "Something went wrong while generating content.", true);
    } finally {
        setLoading(false);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initCopyActions();
    initUploader();
});