const API_URL = "/generate";

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

async function generateMarketing() {
    const formData = new FormData();
    formData.append('company', document.getElementById('company').value);
    formData.append('campaign', document.getElementById('campaign').value);
    formData.append('description', document.getElementById('description').value);
    formData.append('website_url', document.getElementById('website-url').value);

    const fileInput = document.getElementById('supporting-file');
    if (fileInput && fileInput.files && fileInput.files[0]) {
        formData.append('file', fileInput.files[0]);
    }

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

document.addEventListener("DOMContentLoaded", initCopyActions);