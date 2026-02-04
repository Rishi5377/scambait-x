/**
 * ScamBait-X Honeypot - WebSocket Client
 * Real-time chat interface with entity extraction
 */

// ============================================================
// WebSocket Manager with Exponential Backoff Reconnection
// ============================================================

class WebSocketManager {
    constructor(url, handlers) {
        this.url = url;
        this.handlers = handlers;
        this.ws = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectDelay = 30000; // 30 seconds max
        this.baseDelay = 1000; // Start at 1 second
        this.isConnecting = false;
        this.shouldReconnect = true;
    }

    connect() {
        if (this.isConnecting) return;
        this.isConnecting = true;

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                this.handlers.onConnect?.();
                
                // Resume session if reconnecting
                if (this.sessionId) {
                    this.send({
                        type: 'resume_session',
                        session_id: this.sessionId
                    });
                }
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handlers.onMessage?.(data);
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };

            this.ws.onclose = () => {
                this.isConnecting = false;
                this.handlers.onDisconnect?.();
                if (this.shouldReconnect) {
                    this.scheduleReconnect();
                }
            };

            this.ws.onerror = (error) => {
                this.isConnecting = false;
                this.handlers.onError?.(error);
            };
        } catch (e) {
            this.isConnecting = false;
            console.error('WebSocket connection error:', e);
        }
    }

    scheduleReconnect() {
        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.reconnectAttempts),
            this.maxReconnectDelay
        );
        this.reconnectAttempts++;
        
        showToast(`Reconnecting in ${delay / 1000}s...`, 'warning');
        
        setTimeout(() => {
            if (this.shouldReconnect) {
                this.connect();
            }
        }, delay);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    disconnect() {
        this.shouldReconnect = false;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    setSessionId(id) {
        this.sessionId = id;
    }
}


// ============================================================
// App State
// ============================================================

const state = {
    wsManager: null,
    sessionId: null,
    personaId: null,
    scamType: null,
    isAutoMode: false,
    turnCount: 0,
    startTime: null,
    timerInterval: null,
    extractedEntities: {
        upi: [],
        phone: [],
        bank: [],
        url: [],
        crypto: [],
        email: []
    }
};


// ============================================================
// DOM Elements
// ============================================================

const elements = {
    personaSelect: document.getElementById('personaSelect'),
    scamSelect: document.getElementById('scamSelect'),
    startBtn: document.getElementById('startBtn'),
    endBtn: document.getElementById('endBtn'),
    downloadBtn: document.getElementById('downloadBtn'),
    messagesContainer: document.getElementById('messagesContainer'),
    inputContainer: document.getElementById('inputContainer'),
    scammerInput: document.getElementById('scammerInput'),
    sendBtn: document.getElementById('sendBtn'),
    liveIndicator: document.getElementById('liveIndicator'),
    sessionTimer: document.getElementById('sessionTimer'),
    turnCount: document.getElementById('turnCount'),
    modeIndicator: document.getElementById('modeIndicator'),
    upiList: document.getElementById('upiList'),
    phoneList: document.getElementById('phoneList'),
    bankList: document.getElementById('bankList'),
    urlList: document.getElementById('urlList'),
    cryptoList: document.getElementById('cryptoList'),
    toastContainer: document.getElementById('toastContainer')
};


// ============================================================
// Toast Notifications
// ============================================================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    elements.toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}


// ============================================================
// Timer
// ============================================================

function startTimer() {
    state.startTime = Date.now();
    state.timerInterval = setInterval(updateTimer, 1000);
}

function stopTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

function updateTimer() {
    if (!state.startTime) return;
    
    const elapsed = Math.floor((Date.now() - state.startTime) / 1000);
    const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
    const seconds = (elapsed % 60).toString().padStart(2, '0');
    
    elements.sessionTimer.textContent = `${minutes}:${seconds}`;
}


// ============================================================
// UI Updates
// ============================================================

function updateConnectionStatus(connected) {
    if (connected) {
        elements.liveIndicator.classList.add('connected');
        elements.liveIndicator.querySelector('.live-text').textContent = 'LIVE';
    } else {
        elements.liveIndicator.classList.remove('connected');
        elements.liveIndicator.querySelector('.live-text').textContent = 'OFFLINE';
    }
}

function updateTurnCount(count) {
    state.turnCount = count;
    elements.turnCount.textContent = `Turn: ${count}`;
}

function updateMode(mode) {
    const indicator = elements.modeIndicator;
    const icon = indicator.querySelector('.mode-icon');
    const text = indicator.querySelector('.mode-text');
    
    if (mode === 'aggressive') {
        indicator.classList.add('aggressive');
        icon.textContent = '🔥';
        text.textContent = 'AGGRESSIVE';
    } else {
        indicator.classList.remove('aggressive');
        icon.textContent = '🐢';
        text.textContent = 'PATIENCE';
    }
}

function addMessage(role, content) {
    // Remove empty state if present
    const emptyState = elements.messagesContainer.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    // Remove typing indicator if present
    const typing = elements.messagesContainer.querySelector('.typing-indicator');
    if (typing) typing.remove();
    
    const message = document.createElement('div');
    message.className = `message message-${role}`;
    
    const time = new Date().toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    const roleLabel = role === 'scammer' ? '🔴 SCAMMER' : '🟢 HONEYPOT';
    
    message.innerHTML = `
        <div class="message-header">
            <span class="message-role">${roleLabel}</span>
            <span class="message-time">${time}</span>
        </div>
        <div class="message-content">${escapeHtml(content)}</div>
    `;
    
    elements.messagesContainer.appendChild(message);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    
    // Update turn count for honeypot messages
    if (role === 'honeypot') {
        updateTurnCount(state.turnCount + 1);
    }
}

function showTypingIndicator() {
    const existing = elements.messagesContainer.querySelector('.typing-indicator');
    if (existing) return;
    
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span></span><span></span><span></span>';
    
    elements.messagesContainer.appendChild(indicator);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

function updateEntityList(listElement, entities, type) {
    // Clear existing
    listElement.innerHTML = '';
    
    if (entities.length === 0) {
        const emptyLi = document.createElement('li');
        emptyLi.className = 'empty';
        emptyLi.textContent = `No ${type} extracted`;
        listElement.appendChild(emptyLi);
        return;
    }
    
    entities.forEach((entity, index) => {
        const li = document.createElement('li');
        li.textContent = entity;
        
        // Mark new entities
        if (index === entities.length - 1) {
            li.classList.add('new');
        }
        
        listElement.appendChild(li);
    });
}

function addExtractedEntities(entityStrings) {
    entityStrings.forEach(entityStr => {
        if (entityStr.startsWith('UPI:')) {
            const value = entityStr.substring(5).trim();
            if (!state.extractedEntities.upi.includes(value)) {
                state.extractedEntities.upi.push(value);
            }
        } else if (entityStr.startsWith('Phone:')) {
            const value = entityStr.substring(7).trim();
            if (!state.extractedEntities.phone.includes(value)) {
                state.extractedEntities.phone.push(value);
            }
        } else if (entityStr.startsWith('Bank:')) {
            const value = entityStr.substring(6).trim();
            if (!state.extractedEntities.bank.includes(value)) {
                state.extractedEntities.bank.push(value);
            }
        } else if (entityStr.startsWith('URL:')) {
            const value = entityStr.substring(5).trim();
            if (!state.extractedEntities.url.includes(value)) {
                state.extractedEntities.url.push(value);
            }
        } else if (entityStr.startsWith('Crypto:')) {
            const value = entityStr.substring(8).trim();
            if (!state.extractedEntities.crypto.includes(value)) {
                state.extractedEntities.crypto.push(value);
            }
        } else if (entityStr.startsWith('Email:')) {
            const value = entityStr.substring(7).trim();
            if (!state.extractedEntities.email.includes(value)) {
                state.extractedEntities.email.push(value);
            }
        }
    });
    
    // Update UI
    updateEntityList(elements.upiList, state.extractedEntities.upi, 'UPI IDs');
    updateEntityList(elements.phoneList, state.extractedEntities.phone, 'phone numbers');
    updateEntityList(elements.bankList, state.extractedEntities.bank, 'bank accounts');
    updateEntityList(elements.urlList, state.extractedEntities.url, 'URLs');
    updateEntityList(elements.cryptoList, state.extractedEntities.crypto, 'crypto addresses');
}

function resetUI() {
    // Clear messages
    elements.messagesContainer.innerHTML = '<div class="empty-state"><p>Select a persona and start a session to begin</p></div>';
    
    // Reset entities
    state.extractedEntities = { upi: [], phone: [], bank: [], url: [], crypto: [], email: [] };
    updateEntityList(elements.upiList, [], 'UPI IDs');
    updateEntityList(elements.phoneList, [], 'phone numbers');
    updateEntityList(elements.bankList, [], 'bank accounts');
    updateEntityList(elements.urlList, [], 'URLs');
    updateEntityList(elements.cryptoList, [], 'crypto addresses');
    
    // Reset controls
    updateMode('patience');
    updateTurnCount(0);
    elements.sessionTimer.textContent = '00:00';
    elements.inputContainer.style.display = 'none';
    elements.startBtn.disabled = false;
    elements.endBtn.disabled = true;
    elements.downloadBtn.disabled = true;
    
    stopTimer();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


// ============================================================
// WebSocket Message Handlers
// ============================================================

function handleWebSocketMessage(data) {
    console.log('WS Message:', data);
    
    switch (data.type) {
        case 'session_started':
        case 'demo_started':
            state.sessionId = data.session_id;
            state.wsManager.setSessionId(data.session_id);
            showToast(`Session started with ${data.persona?.name || 'persona'}`, 'success');
            break;
            
        case 'session_resumed':
            showToast('Session resumed', 'success');
            updateTurnCount(data.turn_count || 0);
            updateMode(data.mode || 'patience');
            break;
            
        case 'scammer_message':
            addMessage('scammer', data.content);
            break;
            
        case 'honeypot_response':
            // Show typing indicator briefly
            showTypingIndicator();
            
            // Delay actual message based on typing_delay_ms (capped for demo)
            const delay = Math.min(data.typing_delay_ms || 1000, 2000);
            setTimeout(() => {
                addMessage('honeypot', data.content);
                
                // Update entities
                if (data.entities_extracted && data.entities_extracted.length > 0) {
                    addExtractedEntities(data.entities_extracted);
                }
                
                // Update mode
                if (data.mode) {
                    updateMode(data.mode);
                }
            }, delay);
            break;
            
        case 'status_update':
            if (data.mode_switched) {
                updateMode(data.new_mode);
                showToast(`Mode switched to ${data.new_mode}: ${data.reason}`, 'warning');
            }
            break;
            
        case 'demo_ended':
        case 'scam_ended':
            showToast('Session completed', 'success');
            elements.downloadBtn.disabled = false;
            if (data.report) {
                state.lastReport = data.report;
            }
            break;
            
        case 'error':
            showToast(`Error: ${data.error}`, 'error');
            break;
    }
}


// ============================================================
// Actions
// ============================================================

function startSession() {
    const personaId = elements.personaSelect.value;
    const scamType = elements.scamSelect.value;
    
    if (!personaId) {
        showToast('Please select a persona', 'warning');
        return;
    }
    
    state.personaId = personaId;
    state.scamType = scamType;
    state.isAutoMode = !!scamType;
    
    // Determine WebSocket URL
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    
    let wsUrl;
    if (scamType) {
        // Auto demo mode
        wsUrl = `${wsProtocol}//${wsHost}/ws/auto-demo/${personaId}/${scamType}`;
    } else {
        // Manual mode
        wsUrl = `${wsProtocol}//${wsHost}/ws/honeypot/${personaId}`;
    }
    
    // Connect WebSocket
    state.wsManager = new WebSocketManager(wsUrl, {
        onConnect: () => {
            updateConnectionStatus(true);
            showToast('Connected', 'success');
        },
        onDisconnect: () => {
            updateConnectionStatus(false);
        },
        onMessage: handleWebSocketMessage,
        onError: (error) => {
            showToast('Connection error', 'error');
        }
    });
    
    state.wsManager.connect();
    
    // Update UI
    resetUI();
    elements.messagesContainer.innerHTML = '';
    elements.startBtn.disabled = true;
    elements.endBtn.disabled = false;
    
    // Show input for manual mode
    if (!scamType) {
        elements.inputContainer.style.display = 'flex';
    }
    
    startTimer();
}

function endSession() {
    if (state.wsManager) {
        state.wsManager.disconnect();
        state.wsManager = null;
    }
    
    updateConnectionStatus(false);
    showToast('Session ended', 'success');
    
    elements.startBtn.disabled = false;
    elements.endBtn.disabled = true;
    elements.downloadBtn.disabled = false;
    elements.inputContainer.style.display = 'none';
    
    stopTimer();
}

function sendScammerMessage() {
    const message = elements.scammerInput.value.trim();
    if (!message) return;
    
    if (!state.wsManager) {
        showToast('Not connected', 'error');
        return;
    }
    
    // Send message
    const sent = state.wsManager.send({
        type: 'scammer_message',
        content: message
    });
    
    if (sent) {
        addMessage('scammer', message);
        elements.scammerInput.value = '';
    } else {
        showToast('Failed to send message', 'error');
    }
}

async function downloadReport() {
    if (!state.sessionId && !state.lastReport) {
        showToast('No report available', 'warning');
        return;
    }
    
    try {
        let report;
        
        if (state.lastReport) {
            report = state.lastReport;
        } else {
            // Fetch from API
            const response = await fetch(`/api/report/${state.sessionId}`);
            if (!response.ok) throw new Error('Failed to fetch report');
            report = await response.json();
        }
        
        // Download as JSON
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `scambait-report-${state.sessionId || 'demo'}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('Report downloaded', 'success');
    } catch (error) {
        showToast(`Download failed: ${error.message}`, 'error');
    }
}


// ============================================================
// Event Listeners
// ============================================================

elements.startBtn.addEventListener('click', startSession);
elements.endBtn.addEventListener('click', endSession);
elements.downloadBtn.addEventListener('click', downloadReport);
elements.sendBtn.addEventListener('click', sendScammerMessage);

elements.scammerInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendScammerMessage();
    }
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (state.wsManager) {
        state.wsManager.disconnect();
    }
});


// ============================================================
// Initialize
// ============================================================

console.log('🎣 ScamBait-X Honeypot Client initialized');
