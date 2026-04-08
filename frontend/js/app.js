// async function generateMarketing() {
//     const btn = document.getElementById('generateBtn');
//     const btnText = document.getElementById('btnText');
//     const loader = document.getElementById('loader');

//     // UI Feedback: Loading
//     btn.disabled = true;
//     btnText.style.display = 'none';
//     loader.style.display = 'block';

//     const payload = {
//         company: document.getElementById('company').value,
//         campaign: document.getElementById('campaign').value,
//         description: document.getElementById('description').value
//     };

//     try {
//         const response = await fetch('http://127.0.0.1:8000/generate', {
//             method: 'POST',
//             headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify(payload)
//         });

//         const data = await response.json();

//         // Populate sections
//         document.getElementById('email-content').innerText = data.email || "No email generated.";
//         document.getElementById('whatsapp-content').innerText = data.whatsapp || "No message generated.";
//         document.getElementById('linkedin-content').innerText = data.linkedin || "No post generated.";

//     } catch (error) {
//         console.error("Error:", error);
//         alert("Server error. Is main.py running?");
//     } finally {
//         // UI Feedback: Done
//         btn.disabled = false;
//         btnText.style.display = 'block';
//         loader.style.display = 'none';
//     }
// }

const API_URL = "/generate";

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

        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        updateUI(data);

    } catch (error) {
        console.error(error);
        alert("Something went wrong. Check backend/API.");
    } finally {
        setLoading(false);
    }
}