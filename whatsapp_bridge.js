const { 
    default: makeWASocket, 
    useMultiFileAuthState, 
    DisconnectReason,
    downloadMediaMessage 
} = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const os = require('os');

const API_URL = 'http://localhost:18790/v1/chat/completions';
const SESSION_DIR = path.join(__dirname, '.baileys_session');
const REMINDERS_FILE = path.join(os.homedir(), '.zero', 'reminders.json');

// Get Groq key from env
const GROQ_API_KEY = process.env.ZERO_PROVIDERS__GROQ__API_KEY || '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';

// --- Track last sender JID so reminders know where to send ---
let currentUserJid = null;

// --- Bug 1: Robust Tool Call Stripping ---
function cleanResponse(text) {
    if (!text) return text;
    
    // Matches standalone tool-call lines (with optional bullets)
    const toolLineRegex = /^\s*([-*]|\d+\.)?\s*[a-z_][a-z0-9_]*\s*\([^)]*\)\s*$/im;
    
    // 1. Filter out tool-call lines
    const lines = text.split('\n').filter(line => !toolLineRegex.test(line));
    let cleaned = lines.join('\n').trim();
    
    // 2. Drop code blocks that ONLY contain tool calls
    cleaned = cleaned.replace(/```[\s\S]*?```/g, (match) => {
        const inner = match.replace(/```/g, '').trim();
        if (!inner) return '';
        const innerLines = inner.split('\n').filter(l => l.trim().length > 0);
        if (innerLines.every(l => toolLineRegex.test(l))) return '';
        return match;
    });
    
    // 3. Remove inline tool calls that might have leaked
    cleaned = cleaned.replace(/[a-z_][a-z0-9_]*\s*\([^)]*\)/gi, '');
    
    return cleaned.trim();
}

// --- Bug 5: Voice Message Transcription ---
async function transcribeAudio(msg) {
    try {
        console.log('🎤 Downloading voice note...');
        const buffer = await downloadMediaMessage(msg, 'buffer', {});
        
        // Prepare multipart form data for Groq
        const FormData = require('form-data');
        const form = new FormData();
        form.append('file', buffer, { filename: 'voice.ogg', contentType: 'audio/ogg' });
        form.append('model', 'whisper-large-v3-turbo');

        console.log('☁️ Transcribing via Groq Whisper...');
        const response = await axios.post('https://api.groq.com/openai/v1/audio/transcriptions', form, {
            headers: {
                ...form.getHeaders(),
                'Authorization': `Bearer ${GROQ_API_KEY}`
            }
        });

        const text = response.data.text;
        console.log('📝 Transcription:', text);
        return text;
    } catch (err) {
        console.error('❌ Transcription failed:', err.response?.data || err.message);
        return null;
    }
}

// --- Fix #2: Reminder checker ---
function checkAndFireReminders(sock) {
    if (!currentUserJid) return;
    if (!fs.existsSync(REMINDERS_FILE)) return;

    let reminders;
    try {
        reminders = JSON.parse(fs.readFileSync(REMINDERS_FILE, 'utf8'));
    } catch (e) {
        return;
    }

    const now = new Date();
    let changed = false;

    for (const r of reminders) {
        if (r.done || r.fired) continue;
        if (!r.due_iso) continue;

        const due = new Date(r.due_iso);
        if (isNaN(due.getTime())) continue;

        if (due <= now) {
            const targetJid = r.chat_id || currentUserJid;
            const msg = r.note
                ? `🔔 *Reminder:* ${r.title}\n📝 ${r.note}`
                : `🔔 *Reminder:* ${r.title}`;

            sock.sendMessage(targetJid, { text: msg })
                .then(() => console.log(`[Reminder] Fired → ${targetJid}: ${r.title}`))
                .catch(e => console.error(`[Reminder] Send failed: ${e.message}`));

            r.fired = true;
            r.done = true;
            changed = true;
        }
    }

    if (changed) {
        try {
            fs.writeFileSync(REMINDERS_FILE, JSON.stringify(reminders, null, 2));
        } catch (e) {
            console.error('[Reminder] Failed to save:', e.message);
        }
    }
}

async function startBridge() {
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
    
    // Baileys socket
    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false // We handle it manually in connection.update
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            console.log('\n\nScan this QR code with WhatsApp:\n');
            qrcode.generate(qr, { small: true });
        }
        if (connection === 'close') {
            const shouldReconnect = lastDisconnect?.error?.output
                ?.statusCode !== DisconnectReason.loggedOut;
            if (shouldReconnect) {
                console.log('Reconnecting...');
                startBridge();
            }
        }
        if (connection === 'open') {
            console.log('✅ WhatsApp connected!');
            setInterval(() => checkAndFireReminders(sock), 60 * 1000);
            console.log('🔔 Reminder checker started (60s interval)');
        }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;
        
        const msg = messages[0];
        if (!msg.message || msg.key.fromMe) return;
        
        const from = msg.key.remoteJid;
        if (!from) return;

        currentUserJid = from;
        
        let userText = '';

        // Handle text message
        if (msg.message.conversation || msg.message.extendedTextMessage) {
            userText = msg.message.conversation || msg.message.extendedTextMessage.text;
        } 
        // Handle image caption
        else if (msg.message.imageMessage) {
            userText = msg.message.imageMessage.caption || '';
        }
        // Handle voice note (Bug 5)
        else if (msg.message.audioMessage) {
            userText = await transcribeAudio(msg);
            if (!userText) {
                await sock.sendMessage(from, { text: "⚠️ Failed to transcribe voice message." });
                return;
            }
        }
        
        if (!userText || !userText.trim()) return;
        
        console.log('Message from:', from, '→', userText);
        
        try {
            const response = await axios.post(
                API_URL, 
                {
                    model: 'openrouter/free',
                    messages: [{ role: 'user', content: userText }],
                    max_tokens: 1024,
                    channel: 'whatsapp',
                    chat_id: from,
                    session_id: from
                },
                { timeout: 45000 }
            );

            const raw = response.data.choices[0].message.content;
            const reply = cleanResponse(raw);
            
            if (!reply || !reply.trim()) return;

            await sock.sendMessage(from, { text: reply });
            console.log('Replied:', reply.substring(0, 50) + '...');
        } catch (err) {
            console.error('Error:', err.message);
            await sock.sendMessage(from, { 
                text: "My brain is a bit slow right now. Can you try again?" 
            });
        }
    });
}

startBridge().catch(err => console.error('Startup Error:', err));
