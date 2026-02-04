# 🎣 ScamBait-X Honeypot System

An **agentic honeypot system** that impersonates vulnerable victims to engage scammers, dynamically adjusting conversation tactics between slow-burn "patience" mode and rapid "aggressive" extraction mode based on real-time behavioral analysis.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![Groq](https://img.shields.io/badge/LLM-Groq_Llama3_70B-orange)

## ✨ Features

- **3 Victim Personas**: Elderly widow, young professional, small business owner
- **Dynamic Mode Switching**: Automatically switches between patience/aggressive modes based on scammer behavior
- **Real-time Entity Extraction**: UPI IDs, phone numbers, bank accounts, crypto addresses, URLs
- **Hybrid Scam Classification**: Fast regex pre-filter + LLM for detailed analysis
- **WebSocket Interface**: Real-time chat visualization
- **Mock Scammer API**: 3 scripted scam scenarios for testing
- **Intelligence Reports**: Downloadable JSON threat reports

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11 or higher
- A free Groq API key from [console.groq.com](https://console.groq.com)

### 2. Installation

```powershell
# Navigate to project
cd C:\Users\lenovo\.gemini\antigravity\scratch\scambait-x

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r honeypot\requirements.txt
```

### 3. Configuration

Edit `.env` file and add your Groq API key:

```env
GROQ_API_KEY=gsk_your_actual_api_key_here
```

### 4. Run the Server

```powershell
cd honeypot
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open the Interface

Navigate to [http://localhost:8000](http://localhost:8000)

## 📖 Usage

### Manual Mode
1. Select a persona from the dropdown
2. Click "Start Session"
3. Type scammer messages in the input field
4. Watch the honeypot respond and extract entities

### Auto Demo Mode
1. Select a persona
2. Select a mock scam type (Lottery, UPI Fraud, Tech Support)
3. Click "Start Session"
4. Watch the automated conversation unfold

### Download Report
After a session, click "Download Report" to get a JSON intelligence report.

## 🏗️ Architecture

```
scambait-x/
├── honeypot/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Groq client, rate limiter
│   ├── agent/
│   │   ├── personas.py      # 3 victim personas with prompts
│   │   ├── conversation.py  # LangChain conversation agent
│   │   ├── humanizer.py     # Typos, delays, hesitation
│   │   └── mode_switcher.py # Patience ↔ Aggressive logic
│   ├── detection/
│   │   ├── classifier.py    # Hybrid scam classification
│   │   ├── patterns.py      # Regex patterns
│   │   └── extractors.py    # Entity extraction
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   └── mock/
│       └── scammer_api.py   # Mock scammer scripts
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── .env
```

## 🔌 API Endpoints

### REST

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve frontend |
| GET | `/api/health` | Health check |
| GET | `/api/personas` | List personas |
| GET | `/api/scam-types` | List mock scam types |
| GET | `/api/sessions` | List active sessions |
| POST | `/api/sessions?persona_id=X` | Create session |
| GET | `/api/report/{session_id}` | Get intelligence report |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/honeypot/{persona_id}` | Manual honeypot conversation |
| `/ws/mock-scammer/{scam_type}` | Mock scammer connection |
| `/ws/auto-demo/{persona_id}/{scam_type}` | Automated demo |

## ⚠️ Legal Disclaimer

This tool is designed for **research and defensive cybersecurity purposes only**. 

- Do not use to engage with real scammers without legal counsel
- Do not use for any illegal activities
- Check your jurisdiction's laws regarding scam baiting

## 📝 License

MIT License - See LICENSE file for details.

---

Built with 🎣 for cybersecurity research
