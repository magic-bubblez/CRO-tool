const form = document.getElementById('enhanceForm');
const submitBtn = document.getElementById('submitBtn');
const loadingState = document.getElementById('loadingState');
const loadingText = document.getElementById('loadingText');
const errorState = document.getElementById('errorState');
const errorText = document.getElementById('errorText');
const reportSection = document.getElementById('reportSection');
const comparisonSection = document.getElementById('comparisonSection');
const originalFrame = document.getElementById('originalFrame');
const enhancedFrame = document.getElementById('enhancedFrame');

const loadingMessages = [
    'Analyzing ad creative...',
    'Rendering landing page with headless browser...',
    'Generating CRO strategy...',
    'Applying enhancements...',
    'Almost done...',
];

let loadingInterval = null;

function startLoadingAnimation() {
    let index = 0;
    loadingText.textContent = loadingMessages[0];
    loadingInterval = setInterval(() => {
        index = Math.min(index + 1, loadingMessages.length - 1);
        loadingText.textContent = loadingMessages[index];
    }, 6000);
}

function stopLoadingAnimation() {
    if (loadingInterval) {
        clearInterval(loadingInterval);
        loadingInterval = null;
    }
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = document.getElementById('pageUrl').value.trim();
    if (!url) return;

    const adFile = document.getElementById('adFile').files[0];
    if (!adFile) {
        showError('Please upload an ad creative image.');
        return;
    }

    const formData = new FormData();
    formData.append('url', url);
    formData.append('ad_creative', adFile);

    hideError();
    reportSection.classList.add('hidden');
    comparisonSection.classList.add('hidden');
    loadingState.classList.remove('hidden');
    submitBtn.disabled = true;
    startLoadingAnimation();

    try {
        const response = await fetch('/api/enhance', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Enhancement failed');
        }

        const result = await response.json();
        displayResult(result, url);

    } catch (err) {
        showError(err.message || 'Something went wrong. Please try again.');
    } finally {
        loadingState.classList.add('hidden');
        submitBtn.disabled = false;
        stopLoadingAnimation();
    }
});

function displayResult(result, originalUrl) {
    const report = result.report;

    document.getElementById('reportAdSummary').textContent = report.ad_summary || 'N/A';
    document.getElementById('reportPageSummary').textContent = report.page_summary || 'N/A';
    document.getElementById('reportGap').textContent = report.alignment_gap || 'N/A';
    document.getElementById('reportStrategy').textContent = report.cro_strategy || 'N/A';

    const modList = document.getElementById('reportModifications');
    modList.innerHTML = '';
    (report.modifications_applied || []).forEach(mod => {
        const li = document.createElement('li');
        li.textContent = mod;
        modList.appendChild(li);
    });

    // Load pages from backend endpoints
    const enhancedId = result.enhanced_page_id;
    const originalId = result.original_page_id;

    if (originalId) {
        originalFrame.src = '/page/' + originalId;
    } else {
        originalFrame.src = originalUrl;
    }

    if (enhancedId) {
        enhancedFrame.src = '/page/' + enhancedId;
    }

    comparisonSection.classList.remove('hidden');
    reportSection.classList.remove('hidden');

    comparisonSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showError(message) {
    errorText.textContent = message;
    errorState.classList.remove('hidden');
}

function hideError() {
    errorState.classList.add('hidden');
}
