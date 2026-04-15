const { default: makeWASocket, useMultiFileAuthState, 
DisconnectReason } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const os = require('os');

const API_URL = 'http://localhost:18790/v1/chat/completions';
const SESSION_DIR = path.join(__dirname, '.baileys_session');
const REMINDERS_FILE = path.join(os.homedir(), '.zero', 'reminders.json');

// --- Track last sender JID so reminders know where to send ---
let currentUserJid = null;

// --- Fix #1: Strip raw tool call syntax from model responses ---
function cleanResponse(text) {
    if (!text) return text;
    // Remove lines that are purely a function call like: reminder_set("...", ...)
    const lines = text.split('\n').filter(line => {
        const trimmed = line.trim();
        // A "tool call line" looks like: identifier( anything )
        if (/^[a-z_]{2,}\([\s\S]*\)\s*$/.test(trimmed)) return false;
        // Also strip JSON-like tool call blocks
        if (/^"(name|function|arguments)"\s*:/.test(trimmed)) return false;
        return true;
    });
    // Remove common prefixes the model sometimes adds before calling tools
    let result = lines.join('\n').trim();
    // Remove trailing code blocks that look like tool calls
    result = result.replace(/```[\s\S]*?```/g, '').trim();
    return result || text;
}

// --- Fix #2: Reminder checker — polls reminders.json every 60s ---
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
            const msg = r.note
                ? `🔔 *Reminder:* ${r.title}\n📝 ${r.note}`
                : `🔔 *Reminder:* ${r.title}`;

            sock.sendMessage(currentUserJid, { text: msg })
                .then(() => console.log(`[Reminder] Fired → ${currentUserJid}: ${r.title}`))
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
    
    const sock = makeWASocket({
        auth: state
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
            // Start reminder polling once connected
            setInterval(() => checkAndFireReminders(sock), 60 * 1000);
            console.log('🔔 Reminder checker started (polling every 60s)');
        }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;
        
        const msg = messages[0];
        if (!msg.message || msg.key.fromMe) return;
        
        const from = msg.key.remoteJid;
        if (!from) return;

        // Track who we're talking to so reminders go to the right JID
        currentUserJid = from;
        
        const text = msg.message?.conversation 
            || msg.message?.extendedTextMessage?.text 
            || msg.message?.imageMessage?.caption
            || '';
        
        if (!text.trim()) return;
        
        console.log('Message from:', from, '→', text);
        
        try {
            const response = await axios.post(
                'http://localhost:18790/v1/chat/completions', 
                {
                    model: 'openrouter/free',
                    messages: [{ role: 'user', content: text }],
                    max_tokens: 1024
                },
                { timeout: 30000 }
            );
            // Fix #1: clean any leaked tool call syntax before sending
            const raw = response.data.choices[0].message.content;
            const reply = cleanResponse(raw);
            if (!reply || !reply.trim()) return;
            await sock.sendMessage(from, { text: reply });
            console.log('Replied:', reply.substring(0, 50) + '...');
        } catch (err) {
            console.error('Error:', err.message);
            await sock.sendMessage(from, { 
                text: "Having trouble connecting. Try again in a moment." 
            });
        }
    });
}

startBridge();
