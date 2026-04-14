/**
 * whatsapp_bridge.js
 * Zero WhatsApp Bridge using whatsapp-web.js
 *
 * Features:
 *  - QR code in terminal on first run
 *  - Session saved to .ww_session/ (no re-scan after first time)
 *  - Incoming WhatsApp messages → Zero API (http://localhost:18790/v1/chat/completions)
 *  - Zero replies → back to WhatsApp sender
 *  - Voice notes downloaded and referenced in message context
 *  - Per-user conversation history maintained in memory
 */

const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ── Configuration ─────────────────────────────────────────────────────────────
const ZERO_API_URL = process.env.ZERO_API_URL || 'http://localhost:18790/v1/chat/completions';
const ZERO_MODEL   = process.env.ZERO_MODEL   || 'openrouter/auto';
const SESSION_DIR  = path.join(__dirname, '.ww_session');
const MEDIA_DIR    = path.join(os.homedir(), '.zero', 'whatsapp_media');
const MAX_HISTORY  = 20;   // messages per user kept in memory

// ── In-memory conversation histories ─────────────────────────────────────────
// Map<chatId, Array<{role, content}>>
const histories = new Map();

function getHistory(chatId) {
  if (!histories.has(chatId)) histories.set(chatId, []);
  return histories.get(chatId);
}

function pushHistory(chatId, role, content) {
  const h = getHistory(chatId);
  h.push({ role, content });
  // Keep only the last MAX_HISTORY turns
  if (h.length > MAX_HISTORY) h.splice(0, h.length - MAX_HISTORY);
}

// ── Zero API call ─────────────────────────────────────────────────────────────
async function askZero(chatId, userMessage) {
  const history = getHistory(chatId);
  const messages = [
    ...history,
    { role: 'user', content: userMessage },
  ];

  try {
    const response = await axios.post(
      ZERO_API_URL,
      {
        model: ZERO_MODEL,
        messages,
        stream: false,
      },
      {
        timeout: 120_000,
        headers: { 'Content-Type': 'application/json' },
      }
    );

    const reply = response.data?.choices?.[0]?.message?.content || '(no response)';
    // Record both sides for context
    pushHistory(chatId, 'user',      userMessage);
    pushHistory(chatId, 'assistant', reply);
    return reply;
  } catch (err) {
    const detail = err.response?.data ? JSON.stringify(err.response.data) : err.message;
    console.error(`[Zero API error] ${detail}`);
    return `⚠️ Zero is not responding right now. (${err.message})`;
  }
}

// ── Download voice note ───────────────────────────────────────────────────────
async function downloadVoiceNote(msg) {
  try {
    fs.mkdirSync(MEDIA_DIR, { recursive: true });
    const media = await msg.downloadMedia();
    if (!media) return null;

    const ext  = media.mimetype.split('/')[1]?.split(';')[0] || 'ogg';
    const name = `voice_${Date.now()}.${ext}`;
    const dest = path.join(MEDIA_DIR, name);
    fs.writeFileSync(dest, Buffer.from(media.data, 'base64'));
    console.log(`[Voice] Saved to ${dest}`);
    return dest;
  } catch (err) {
    console.error(`[Voice] Download failed: ${err.message}`);
    return null;
  }
}

// ── WhatsApp Client ───────────────────────────────────────────────────────────
const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESSION_DIR }),
  puppeteer: {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  },
  webVersionCache: {
    type: 'remote',
    remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1017054896-alpha/index.html',
  },
});

// QR code — displayed only once (subsequent starts reuse saved session)
client.on('qr', (qr) => {
  console.log('\n📱 Scan this QR code with WhatsApp:');
  console.log('   Open WhatsApp → Settings → Linked Devices → Link a Device\n');
  qrcode.generate(qr, { small: true });
  console.log('\nWaiting for scan...\n');
});

client.on('authenticated', () => {
  console.log('✅ WhatsApp authenticated — session saved to .ww_session/');
});

client.on('auth_failure', (msg) => {
  console.error(`❌ Auth failed: ${msg}`);
  console.error('Delete .ww_session/ and restart to re-scan the QR code.');
  process.exit(1);
});

client.on('ready', () => {
  const name = client.info?.pushname || 'Unknown';
  const num  = client.info?.wid?.user || 'Unknown';
  console.log(`\n🟢 WhatsApp connected as ${name} (+${num})`);
  console.log(`   Forwarding messages → ${ZERO_API_URL}\n`);
});

client.on('disconnected', (reason) => {
  console.warn(`⚠️  Disconnected: ${reason}`);
  console.warn('Attempting to reconnect...');
  client.initialize();
});

// ── Incoming message handler ──────────────────────────────────────────────────
client.on('message', async (msg) => {
  // Ignore status broadcasts and our own messages
  if (msg.from === 'status@broadcast') return;
  if (msg.fromMe) return;

  const chatId  = msg.from;   // e.g. "15551234567@c.us"
  const contact = await msg.getContact();
  const name    = contact.pushname || contact.name || chatId;

  let userText = msg.body || '';

  // ── Handle voice notes ──────────────────────────────────────────────────
  if (msg.hasMedia && msg.type === 'ptt') {
    console.log(`[Voice note] from ${name} (${chatId})`);
    const voicePath = await downloadVoiceNote(msg);
    if (voicePath) {
      userText = `[Voice Note received — audio saved at: ${voicePath}]\n` +
                 `Please acknowledge you received a voice note and let me know if you can process it.`;
    } else {
      userText = '[Voice Note received — could not download audio]';
    }
  }

  // ── Handle other media (images, docs) ──────────────────────────────────
  if (msg.hasMedia && msg.type !== 'ptt') {
    const caption = msg.body ? ` Caption: "${msg.body}"` : '';
    userText = `[${msg.type.toUpperCase()} received${caption}]`;
  }

  if (!userText.trim()) return;

  console.log(`[${new Date().toLocaleTimeString()}] ${name}: ${userText.slice(0, 80)}${userText.length > 80 ? '…' : ''}`);

  // Show typing indicator
  const chat = await msg.getChat();
  await chat.sendStateTyping();

  // Get Zero's reply
  const reply = await askZero(chatId, userText);

  // Stop typing indicator and send reply
  await chat.clearState();
  await msg.reply(reply);

  console.log(`[${new Date().toLocaleTimeString()}] Zero → ${name}: ${reply.slice(0, 80)}${reply.length > 80 ? '…' : ''}`);
});

// ── Startup ───────────────────────────────────────────────────────────────────
console.log('');
console.log('╔══════════════════════════════════════╗');
console.log('║   Zero — WhatsApp Bridge             ║');
console.log('╚══════════════════════════════════════╝');
console.log(`  API endpoint : ${ZERO_API_URL}`);
console.log(`  Session dir  : ${SESSION_DIR}`);
console.log(`  Media dir    : ${MEDIA_DIR}`);
console.log('');

client.initialize();

// Graceful shutdown
process.on('SIGINT',  async () => { await client.destroy(); process.exit(0); });
process.on('SIGTERM', async () => { await client.destroy(); process.exit(0); });
