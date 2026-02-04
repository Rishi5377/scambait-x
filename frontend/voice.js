/**
 * ScamBait-X Conversational AI Agent
 * Real-time speech recognition with auto-speaking AI
 */

// State
let isListening = false;
let recognition = null;
let ws = null;
let currentPersona = 'young_professional';
let scamScore = 0;
let isAIActive = false;
let transcriptHistory = [];
let lastAIResponse = '';
let autoSpeak = true; // Enable auto-speak by default
let isSpeaking = false;
let conversationTurns = 0;

// DOM Elements
const callButton = document.getElementById('callButton');
const callIcon = document.getElementById('callIcon');
const callText = document.getElementById('callText');
const callStatus = document.getElementById('callStatus');
const connectionStatus = document.getElementById('connectionStatus');
const scamScoreEl = document.getElementById('scamScore');
const scamMeter = document.getElementById('scamMeter');
const normalMode = document.getElementById('normalMode');
const aiMode = document.getElementById('aiMode');
const transcriptionContent = document.getElementById('transcriptionContent');
const interimText = document.getElementById('interimText');
const listeningIndicator = document.getElementById('listeningIndicator');
const aiContent = document.getElementById('aiContent');
const speakButton = document.getElementById('speakButton');
const aiStatus = document.getElementById('aiStatus');
const entitiesContent = document.getElementById('entitiesContent');
const entityCount = document.getElementById('entityCount');
const logContent = document.getElementById('logContent');

// AI Greetings (spoken when call starts - AI answers first)
const AI_GREETINGS = {
    'elderly_widow': "Hello? Who is this calling?",
    'young_professional': "Yeah, hello?",
    'small_business_owner': "Hello, this is Priya speaking."
};

// Probing questions (AI asks these to understand the caller)
const PROBING_QUESTIONS = [
    "May I know who is calling please?",
    "Are you calling from which company?",
    "What is this regarding?",
    "How did you get my number?",
    "Can you please explain more slowly?"
];

// Initialize Speech Recognition
function initSpeechRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        addLog('Speech recognition not supported. Please use Chrome.', 'danger');
        callButton.disabled = true;
        return false;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-IN';

    recognition.onstart = () => {
        addLog('Microphone activated - listening to caller', 'success');
        listeningIndicator.classList.add('active');
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }

        interimText.textContent = interimTranscript;

        if (finalTranscript && !isSpeaking) {
            processTranscript(finalTranscript);
        }
    };

    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'no-speech') {
            // Don't show error, just keep listening
        } else if (event.error === 'not-allowed') {
            addLog('Microphone access denied. Please allow microphone.', 'danger');
            stopListening();
        }
    };

    recognition.onend = () => {
        listeningIndicator.classList.remove('active');
        if (isListening && !isSpeaking) {
            try {
                recognition.start();
            } catch (e) {
                console.log('Recognition restart failed:', e);
            }
        }
    };

    return true;
}

// Initialize WebSocket
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/voice/${currentPersona}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        connectionStatus.classList.add('connected');
        connectionStatus.querySelector('span:last-child').textContent = 'Connected';
        addLog('Connected to AI server', 'success');

        // AI answers the call with a greeting
        setTimeout(() => {
            aiGreeting();
        }, 500);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addLog('Connection error', 'danger');
    };

    ws.onclose = () => {
        connectionStatus.classList.remove('connected');
        connectionStatus.querySelector('span:last-child').textContent = 'Disconnected';

        setTimeout(() => {
            if (isListening) {
                initWebSocket();
            }
        }, 3000);
    };
}

// AI Greeting - AI speaks first when call starts
function aiGreeting() {
    const greeting = AI_GREETINGS[currentPersona] || "Hello?";
    displayAIResponse(greeting);
    speakText(greeting, () => {
        addLog('AI: Waiting for caller response...', 'info');
        callStatus.textContent = 'Listening to caller...';
    });
}

// Process transcript from caller
function processTranscript(text) {
    conversationTurns++;

    const now = new Date().toLocaleTimeString();
    transcriptHistory.push({ time: now, text: text, sender: 'caller' });
    updateTranscriptDisplay();

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'transcript',
            content: text,
            timestamp: now,
            turn: conversationTurns
        }));
    }

    addLog(`📞 Caller: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}"`, 'info');
}

// Update transcript display
function updateTranscriptDisplay() {
    if (transcriptHistory.length === 0) {
        transcriptionContent.innerHTML = '<p class="placeholder">Listening for caller...</p>';
        return;
    }

    transcriptionContent.innerHTML = transcriptHistory
        .map(t => {
            const icon = t.sender === 'ai' ? '🤖' : '📞';
            const color = t.sender === 'ai' ? '#aa44ff' : '#00aaff';
            return `<p><span style="color: ${color}">${icon} [${t.time}]</span> ${t.text}</p>`;
        })
        .join('');

    transcriptionContent.scrollTop = transcriptionContent.scrollHeight;
}

// Handle server messages
function handleServerMessage(data) {
    switch (data.type) {
        case 'scam_analysis':
            updateScamScore(data.score, data.indicators);
            break;

        case 'ai_response':
            displayAIResponse(data.content);
            // Auto-speak the response
            if (autoSpeak) {
                speakText(data.content);
            }
            break;

        case 'entities_found':
            updateEntities(data.entities);
            break;

        case 'mode_switch':
            if (data.is_scammer) {
                activateAIMode(data.reason);
            } else {
                // Forward call simulation
                simulateCallForward();
            }
            break;

        case 'error':
            addLog(`Error: ${data.message}`, 'danger');
            break;
    }
}

// Speak text using TTS
function speakText(text, onComplete = null) {
    if (!text) return;

    // Stop listening while speaking
    isSpeaking = true;
    if (recognition) {
        try { recognition.stop(); } catch (e) { }
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-IN';
    utterance.rate = 0.9;
    utterance.pitch = 1.0;

    const voices = speechSynthesis.getVoices();
    const preferredVoice = voices.find(v => v.lang === 'en-IN') ||
        voices.find(v => v.name.includes('Female')) ||
        voices.find(v => v.lang.startsWith('en'));
    if (preferredVoice) {
        utterance.voice = preferredVoice;
    }

    utterance.onstart = () => {
        aiStatus.textContent = '🔊 AI Speaking...';
        callStatus.textContent = 'AI is speaking...';
        speakButton.disabled = true;
        listeningIndicator.classList.remove('active');
    };

    utterance.onend = () => {
        isSpeaking = false;
        aiStatus.textContent = 'Listening for response...';
        callStatus.textContent = 'Listening to caller...';
        speakButton.disabled = false;

        // Resume listening after speaking
        if (isListening && recognition) {
            setTimeout(() => {
                try { recognition.start(); } catch (e) { }
            }, 300);
        }

        if (onComplete) onComplete();
    };

    speechSynthesis.speak(utterance);

    // Add to transcript
    const now = new Date().toLocaleTimeString();
    transcriptHistory.push({ time: now, text: text, sender: 'ai' });
    updateTranscriptDisplay();
}

// Update scam score meter
function updateScamScore(score, indicators = []) {
    scamScore = score;
    const percentage = Math.round(score * 100);

    scamScoreEl.textContent = `${percentage}%`;
    scamMeter.style.width = `${percentage}%`;

    if (percentage < 40) {
        scamScoreEl.className = 'meter-value';
        scamMeter.className = 'meter-fill';
    } else if (percentage < 60) {
        scamScoreEl.className = 'meter-value warning';
        scamMeter.className = 'meter-fill warning';
    } else {
        scamScoreEl.className = 'meter-value danger';
        scamMeter.className = 'meter-fill danger';
    }

    // Activate AI mode if scammer detected
    if (percentage >= 60 && !isAIActive) {
        const reason = indicators.length > 0
            ? `Detected: ${indicators.slice(0, 3).join(', ')}`
            : 'High scam probability detected';
        activateAIMode(reason);
    }
}

// Activate AI agent mode (scammer detected)
function activateAIMode(reason) {
    isAIActive = true;
    normalMode.classList.add('hidden');
    aiMode.classList.remove('hidden');

    addLog(`🚨 SCAMMER DETECTED: ${reason}`, 'danger');
    addLog('AI Agent engaging scammer...', 'warning');

    callButton.style.borderColor = '#ff4444';
    callButton.style.background = 'rgba(255, 68, 68, 0.2)';

    // Announce scammer detection
    speakText("Oh my goodness! Tell me more about this...");
}

// Simulate call forwarding (for normal callers)
function simulateCallForward() {
    addLog('✅ Normal caller detected - would forward to you', 'success');
    aiStatus.textContent = '📞 Forwarding call to owner...';

    speakText("Please hold, I'm transferring you to the owner.", () => {
        addLog('Call forwarding simulated', 'info');
    });
}

// Display AI response in UI
function displayAIResponse(content) {
    lastAIResponse = content;
    aiContent.innerHTML = `<p>${content}</p>`;
    speakButton.disabled = false;
    addLog(`🤖 AI: "${content.substring(0, 50)}..."`, 'success');
}

// Manual speak button
function speakResponse() {
    if (lastAIResponse) {
        speakText(lastAIResponse);
    }
}

// Update entities display
function updateEntities(entities) {
    if (!entities || Object.keys(entities).length === 0) {
        entitiesContent.innerHTML = '<p class="placeholder">Scammer details will appear here...</p>';
        entityCount.textContent = '0 items';
        return;
    }

    let html = '';
    let totalCount = 0;

    const typeLabels = {
        upi_ids: '💳 UPI',
        phone_numbers: '📱 Phone',
        bank_accounts: '🏦 Bank',
        crypto_addresses: '₿ Crypto',
        urls: '🔗 URL',
        emails: '📧 Email'
    };

    for (const [type, values] of Object.entries(entities)) {
        if (values && values.length > 0) {
            for (const value of values) {
                html += `
                    <div class="entity-item">
                        <span class="entity-type">${typeLabels[type] || type}</span>
                        <span class="entity-value">${value}</span>
                    </div>
                `;
                totalCount++;
            }
        }
    }

    entitiesContent.innerHTML = html || '<p class="placeholder">Scammer details will appear here...</p>';
    entityCount.textContent = `${totalCount} items`;
}

// Toggle call
function toggleCall() {
    if (isListening) {
        stopListening();
    } else {
        startListening();
    }
}

// Start call - AI answers
function startListening() {
    if (!recognition && !initSpeechRecognition()) {
        return;
    }

    isListening = true;
    isAIActive = false;
    isSpeaking = false;
    transcriptHistory = [];
    conversationTurns = 0;

    callButton.classList.add('active');
    callIcon.textContent = '🔴';
    callText.textContent = 'End Call';
    callStatus.textContent = 'AI Answering...';

    normalMode.classList.remove('hidden');
    aiMode.classList.add('hidden');

    updateScamScore(0);
    updateTranscriptDisplay();
    aiContent.innerHTML = '<p class="placeholder">AI will engage with the caller...</p>';
    entitiesContent.innerHTML = '<p class="placeholder">Scammer details will appear here...</p>';
    speakButton.disabled = true;

    initWebSocket();

    try {
        recognition.start();
        addLog('📞 Incoming call answered by AI', 'success');
    } catch (e) {
        console.error('Failed to start recognition:', e);
        addLog('Failed to start microphone', 'danger');
    }
}

// End call
function stopListening() {
    isListening = false;
    isSpeaking = false;
    speechSynthesis.cancel();

    callButton.classList.remove('active');
    callIcon.textContent = '📞';
    callText.textContent = 'Answer Call';
    callStatus.textContent = 'Click to simulate incoming call';
    callButton.style.borderColor = '';
    callButton.style.background = '';

    listeningIndicator.classList.remove('active');

    if (recognition) {
        recognition.stop();
    }

    if (ws) {
        ws.close();
    }

    // Summary
    if (isAIActive) {
        addLog(`📊 Call ended - Scammer engaged for ${conversationTurns} turns`, 'warning');
    } else {
        addLog('📞 Call ended', 'info');
    }
}

// Add log entry
function addLog(message, type = 'info') {
    const now = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-time">${now}</span>
        <span class="log-message">${message}</span>
    `;

    logContent.appendChild(entry);
    logContent.scrollTop = logContent.scrollHeight;
}

// Clear log
function clearLog() {
    logContent.innerHTML = `
        <div class="log-entry info">
            <span class="log-time">${new Date().toLocaleTimeString()}</span>
            <span class="log-message">Log cleared</span>
        </div>
    `;
}

// Persona is auto-selected: young_professional (Tech-savvy skeptic)
// No user selection needed

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    speechSynthesis.getVoices();

    if (initSpeechRecognition()) {
        addLog('📞 Waiting for incoming call...', 'success');
        addLog('Click "Answer Call" to simulate an incoming call', 'info');
    }

    // Update button text
    callText.textContent = 'Answer Call';
    callStatus.textContent = 'Click to simulate incoming call';
});

speechSynthesis.onvoiceschanged = () => {
    speechSynthesis.getVoices();
};
