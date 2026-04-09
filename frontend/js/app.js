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

function updateUI(data) {
    document.getElementById('email-content').innerText =
        data.email || "No email generated.";

    document.getElementById('whatsapp-content').innerText =
        data.whatsapp || "No message generated.";

    document.getElementById('linkedin-content').innerText =
        data.linkedin || "No post generated.";
}

async function generateMarketing() {
    const payload = {
        company: document.getElementById('company').value,
        campaign: document.getElementById('campaign').value,
        description: document.getElementById('description').value
    };

    try {
        setLoading(true);
        setStatus('');

        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
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