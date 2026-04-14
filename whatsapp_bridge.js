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
        auth: state,
        printQRInTerminal: true
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
        if (qr) {
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
            console.log('WhatsApp connected!');
        }
    });

    sock.ev.on('messages.upsert', async ({ messages }) => {
        const msg = messages[0];
        if (!msg.message || msg.key.fromMe) return;

        const from = msg.key.remoteJid;
        const text = msg.message.conversation || 
                     msg.message.extendedTextMessage?.text || '';
        
        if (!text) return;

        try {
            const response = await axios.post(API_URL, {
                model: 'openrouter/free',
                messages: [{ role: 'user', content: text }]
            });
            const reply = response.data.choices[0].message.content;
            await sock.sendMessage(from, { text: reply });
        } catch (err) {
            console.error('Error:', err.message);
            await sock.sendMessage(from, { 
                text: "I'm having trouble connecting. Try again in a moment." 
            });
        }
    });
}

startBridge();
