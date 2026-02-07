/* ============================================================
   DUBMASTER — APP.JS
   All interactive logic, particle background, API integration
   ============================================================ */

// API Base URL (change this when deploying)
const API_BASE_URL = window.location.origin;

// ===================== PARTICLE BACKGROUND =====================
(function () {
    const canvas = document.getElementById('particleCanvas');
    const ctx = canvas.getContext('2d');
    let particles = [];
    let w, h;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }

    function createParticle() {
        return {
            x: Math.random() * w,
            y: Math.random() * h,
            r: Math.random() * 1.5 + 0.3,
            dx: (Math.random() - 0.5) * 0.3,
            dy: (Math.random() - 0.5) * 0.3,
            opacity: Math.random() * 0.4 + 0.05,
            hue: Math.random() > 0.7 ? 190 : 160 // cyan or green-ish
        };
    }

    function init() {
        resize();
        particles = [];
        for (let i = 0; i < 80; i++) particles.push(createParticle());
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);
        particles.forEach((p, i) => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${p.hue}, 100%, 60%, ${p.opacity})`;
            ctx.fill();

            // Draw lines to nearby particles
            for (let j = i + 1; j < particles.length; j++) {
                const q = particles[j];
                const dist = Math.hypot(p.x - q.x, p.y - q.y);
                if (dist < 140) {
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(q.x, q.y);
                    ctx.strokeStyle = `hsla(190, 100%, 60%, ${0.08 * (1 - dist / 140)})`;
                    ctx.lineWidth = 0.6;
                    ctx.stroke();
                }
            }

            // Update
            p.x += p.dx;
            p.y += p.dy;
            if (p.x < 0 || p.x > w) p.dx *= -1;
            if (p.y < 0 || p.y > h) p.dy *= -1;
        });
        requestAnimationFrame(draw);
    }

    window.addEventListener('resize', init);
    init();
    draw();
})();


// ===================== NAV ACTIVE STATE =====================
window.addEventListener('scroll', () => {
    const sections = ['home', 'features', 'how-it-works', 'dubbing-studio'];
    const links = document.querySelectorAll('.nav-link');
    let current = 'home';
    sections.forEach(id => {
        const el = document.getElementById(id);
        if (el && window.scrollY >= el.offsetTop - 200) current = id;
    });
    links.forEach(link => {
        link.classList.toggle('active', link.getAttribute('href') === '#' + current);
    });
});


// ===================== INPUT MODE SWITCH =====================
function switchMode(mode) {
    const uploadArea = document.getElementById('uploadArea');
    const linkArea = document.getElementById('linkArea');
    const uploadToggle = document.getElementById('uploadToggle');
    const linkToggle = document.getElementById('linkToggle');

    if (mode === 'upload') {
        uploadArea.classList.add('active');
        uploadArea.style.display = 'block';
        linkArea.style.display = 'none';
        uploadToggle.classList.add('active');
        linkToggle.classList.remove('active');
    } else {
        linkArea.style.display = 'block';
        uploadArea.classList.remove('active');
        uploadArea.style.display = 'none';
        linkToggle.classList.add('active');
        uploadToggle.classList.remove('active');
    }
}


// ===================== DRAG & DROP =====================
const dropzone = document.getElementById('dropzone');

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
});

dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
        setFile(file);
    } else {
        alert('Please drop a valid video file (MP4, MKV, AVI, MOV).');
    }
});


// ===================== FILE HANDLING =====================
let selectedFile = null;

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) setFile(file);
}

function setFile(file) {
    selectedFile = file;
    document.getElementById('fileName').textContent = file.name;
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
    document.getElementById('fileSize').textContent = sizeMB + ' MB';
    document.getElementById('filePreview').style.display = 'flex';
    document.getElementById('dropzone').style.display = 'none';
}

function removeFile() {
    selectedFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('filePreview').style.display = 'none';
    document.getElementById('dropzone').style.display = 'block';
}


// ===================== LINK FETCH - REAL API =====================
let videoFetched = false;
let videoUrl = '';

async function fetchVideo() {
    const url = document.getElementById('videoLink').value.trim();
    if (!url) {
        alert('Please paste a video URL.');
        return;
    }

    // Validate basic URL
    try { new URL(url); } catch (_) {
        alert('Please enter a valid URL.');
        return;
    }

    const btn = document.querySelector('.fetch-btn');
    btn.innerHTML = '<span>Fetching...</span>';
    btn.disabled = true;

    try {
        // Call real API to get video info
        const response = await fetch(`${API_BASE_URL}/api/video-info?url=${encodeURIComponent(url)}`, {
            method: 'POST',
        });

        const data = await response.json();

        if (data.success) {
            videoFetched = true;
            videoUrl = url;

            document.getElementById('videoTitle').textContent = data.title || 'Video';
            document.getElementById('videoDuration').textContent = 'Duration: ' + (data.duration || 'Unknown');
            document.getElementById('linkPreview').style.display = 'flex';

            btn.innerHTML = '<span>Fetched ✓</span>';
            btn.style.background = 'var(--accent2)';
        } else {
            throw new Error(data.error || 'Failed to fetch video info');
        }
    } catch (error) {
        console.error('Fetch error:', error);

        // Fallback: assume URL is valid if API fails
        videoFetched = true;
        videoUrl = url;

        let title = 'Video from ' + (new URL(url).hostname.replace('www.', ''));
        document.getElementById('videoTitle').textContent = title;
        document.getElementById('videoDuration').textContent = 'Duration: Loading...';
        document.getElementById('linkPreview').style.display = 'flex';

        btn.innerHTML = '<span>Ready ✓</span>';
        btn.style.background = 'var(--accent2)';
    }

    btn.disabled = false;
}


// ===================== LANGUAGE SWAP =====================
function swapLangs() {
    const src = document.getElementById('sourceLang');
    const tgt = document.getElementById('targetLang');
    const tmp = src.value;
    src.value = tgt.value;
    tgt.value = tmp;
}


// ===================== ADVANCED OPTIONS =====================
function toggleAdvanced() {
    const panel = document.getElementById('advancedPanel');
    const arrow = document.getElementById('advArrow');
    panel.classList.toggle('open');
    arrow.style.transform = panel.classList.contains('open') ? 'rotate(180deg)' : 'rotate(0)';
}


// ===================== START DUBBING - REAL API =====================
let currentJobId = null;
let statusInterval = null;

async function startDubbing() {
    // Validation
    const isUpload = document.getElementById('uploadArea').style.display !== 'none';
    if (isUpload && !selectedFile) {
        alert('Please upload a video file or switch to "Video Link" mode.');
        return;
    }
    if (!isUpload && !videoFetched) {
        alert('Please paste a video URL and click Fetch first.');
        return;
    }

    // Show processing modal
    document.getElementById('processingModal').style.display = 'flex';
    resetProgress();

    try {
        let response;

        if (isUpload) {
            // Upload file
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('source_lang', document.getElementById('sourceLang').value);
            formData.append('target_lang', document.getElementById('targetLang').value);
            formData.append('voice_gender', document.getElementById('voiceGender').value);
            formData.append('preserve_background', document.getElementById('keepBGMusic').checked);
            formData.append('dub_volume', document.getElementById('dubVolume').value);

            response = await fetch(`${API_BASE_URL}/api/dub/upload`, {
                method: 'POST',
                body: formData,
            });
        } else {
            // Use video URL
            const requestBody = {
                video_url: videoUrl,
                source_lang: document.getElementById('sourceLang').value,
                target_lang: document.getElementById('targetLang').value,
                voice_gender: document.getElementById('voiceGender').value,
                preserve_background: document.getElementById('keepBGMusic').checked,
                dub_volume: parseInt(document.getElementById('dubVolume').value),
            };

            response = await fetch(`${API_BASE_URL}/api/dub`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
            });
        }

        const data = await response.json();

        if (data.job_id) {
            currentJobId = data.job_id;
            // Start polling for status
            pollJobStatus();
        } else {
            throw new Error(data.detail || 'Failed to start dubbing');
        }
    } catch (error) {
        console.error('Dubbing error:', error);
        alert('Failed to start dubbing: ' + error.message);
        document.getElementById('processingModal').style.display = 'none';
    }
}


// ===================== POLL JOB STATUS =====================
function pollJobStatus() {
    if (statusInterval) {
        clearInterval(statusInterval);
    }

    statusInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/status/${currentJobId}`);
            const status = await response.json();

            updateProgressUI(status);

            if (status.status === 'completed') {
                clearInterval(statusInterval);
                statusInterval = null;
                setTimeout(() => {
                    document.getElementById('processingModal').style.display = 'none';
                    showResult();
                }, 1000);
            } else if (status.status === 'failed') {
                clearInterval(statusInterval);
                statusInterval = null;
                alert('Dubbing failed: ' + (status.error || status.message));
                document.getElementById('processingModal').style.display = 'none';
            }
        } catch (error) {
            console.error('Status poll error:', error);
        }
    }, 1500); // Poll every 1.5 seconds
}


// ===================== UPDATE PROGRESS UI =====================
function updateProgressUI(status) {
    const currentStep = status.step || 0;
    const stepNames = ['Downloading', 'Extracting Audio', 'Transcribing Speech', 'Translating Dialogue', 'Synthesizing Voice', 'Mixing & Rendering'];

    // Update modal status text
    document.getElementById('modalStatus').textContent = status.message || stepNames[currentStep];

    // Update step states
    for (let i = 1; i <= 5; i++) {
        const stepEl = document.getElementById('step' + i);
        const barEl = document.getElementById('bar' + i);

        if (i < currentStep) {
            // Completed step
            stepEl.classList.remove('active');
            stepEl.classList.add('done');
            barEl.style.width = '100%';
        } else if (i === currentStep) {
            // Current step
            stepEl.classList.add('active');
            stepEl.classList.remove('done');
            barEl.style.width = status.progress + '%';
        } else {
            // Future step
            stepEl.classList.remove('active', 'done');
            barEl.style.width = '0%';
        }
    }
}


// ===================== PROCESSING SIMULATION (FALLBACK) =====================
function resetProgress() {
    for (let i = 1; i <= 5; i++) {
        const step = document.getElementById('step' + i);
        step.classList.remove('active', 'done');
        document.getElementById('bar' + i).style.width = '0%';
    }
    document.getElementById('step1').classList.add('active');
    document.getElementById('modalStatus').textContent = 'Initializing...';
}


// ===================== SHOW RESULT =====================
function showResult() {
    const targetLang = document.getElementById('targetLang');
    const langName = targetLang.options[targetLang.selectedIndex].text.replace(/^.\s*/, '');
    const quality = document.getElementById('outputQuality');
    const qualityText = quality.options[quality.selectedIndex].text;

    document.getElementById('resultLang').textContent = langName;
    document.getElementById('resultDuration').textContent = 'Processing complete';
    document.getElementById('resultQuality').textContent = qualityText;

    document.getElementById('resultModal').style.display = 'flex';
}


// ===================== DOWNLOAD - REAL API =====================
function downloadVideo() {
    if (currentJobId) {
        // Download from real API
        window.open(`${API_BASE_URL}/api/download/${currentJobId}`, '_blank');
    } else {
        // Fallback demo download
        const targetLang = document.getElementById('targetLang').value;
        const blob = new Blob(
            ['[DubMaster Demo — Dubbed Video Placeholder]\n\nThis is a demo application.\nIn production, this would be the actual dubbed video file.\n\nTarget Language: ' + targetLang + '\nGenerated: ' + new Date().toLocaleString()],
            { type: 'video/mp4' }
        );
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'dubbed_video_' + targetLang + '.mp4';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

function downloadSubtitles() {
    if (currentJobId) {
        // Download from real API
        const targetLang = document.getElementById('targetLang').value;
        window.open(`${API_BASE_URL}/api/download/${currentJobId}/subtitles?lang=${targetLang}`, '_blank');
    } else {
        // Fallback demo download
        const targetLang = document.getElementById('targetLang').value;
        const srtContent = `1
00:00:01,000 --> 00:00:04,500
Welcome to the dubbed version of this movie.

2
00:00:05,000 --> 00:00:09,200
This subtitle file was generated by DubMaster AI.

3
00:00:10,000 --> 00:00:14,800
The dialogue has been translated and synchronized.

4
00:00:15,500 --> 00:00:20,000
Enjoy the movie in your chosen language!

`;
        const blob = new Blob([srtContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'subtitles_' + targetLang + '.srt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}


// ===================== CLOSE RESULT =====================
function closeResult() {
    document.getElementById('resultModal').style.display = 'none';

    // Reset video player
    const video = document.getElementById('previewVideo');
    const placeholder = document.getElementById('videoPlaceholder');

    video.pause();
    video.src = '';
    video.style.display = 'none';
    video.onloadeddata = null;
    video.onerror = null;

    placeholder.innerHTML = '<span>Click "Preview" to watch</span>';
    placeholder.style.display = 'flex';

    currentJobId = null;
}


// ===================== VIDEO PREVIEW =====================
function loadPreview() {
    if (!currentJobId) {
        alert('No video available for preview');
        return;
    }

    const video = document.getElementById('previewVideo');
    const placeholder = document.getElementById('videoPlaceholder');

    // Show loading state
    placeholder.innerHTML = '<span style="color: var(--accent1);">Loading preview...</span>';

    // Set video source to the API endpoint
    const videoUrl = `${API_BASE_URL}/api/download/${currentJobId}`;

    // Add event listeners for proper loading
    video.onloadeddata = function () {
        video.style.display = 'block';
        placeholder.style.display = 'none';
        video.play().catch(e => {
            console.log('Auto-play prevented:', e);
        });
    };

    video.onerror = function () {
        placeholder.innerHTML = '<span style="color: #ff6b6b;">Failed to load video. Try downloading instead.</span>';
        console.error('Video load error');
    };

    // Force reload
    video.src = videoUrl;
    video.load();
}


// ===================== SMOOTH SCROLL FOR NAV =====================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});
