const { default: makeWASocket, useMultiFileAuthState, 
DisconnectReason } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const path = require('path');

const API_URL = 'http://localhost:18790/v1/chat/completions';
const SESSION_DIR = path.join(__dirname, '.baileys_session');

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
        }
    });

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;
        
        const msg = messages[0];
        if (!msg.message || msg.key.fromMe) return;
        
        const from = msg.key.remoteJid;
        if (!from) return;
        
        const text = msg.message?.conversation 
            || msg.message?.extendedTextMessage?.text 
            || msg.message?.imageMessage?.caption
            || '';
        
        if (!text.trim()) return;
        
        console.log('Message from:', from, '→', text);
        
        try {
            const axios = require('axios');
            const response = await axios.post(
                'http://localhost:18790/v1/chat/completions', 
                {
                    model: 'openrouter/free',
                    messages: [{ role: 'user', content: text }],
                    max_tokens: 1024
                },
                { timeout: 30000 }
            );
            const reply = response.data.choices[0].message.content;
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
