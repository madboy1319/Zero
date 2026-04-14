/**
 * whatsapp_bridge.js — Zero WhatsApp Bridge (Baileys edition)
 *
 * Uses @whiskeysockets/baileys — no Puppeteer, works on Android/Termux.
 *
 * Features:
 *  - QR code in terminal on first run
 *  - Auth state saved to .baileys_session/ (no re-scan after first time)
 *  - Incoming WhatsApp messages → Zero API (/v1/chat/completions)
 *  - Zero reply → back to WhatsApp sender
 *  - Voice notes downloaded and referenced in message context
 *  - Auto-reconnect on disconnect
 *  - Per-user conversation history (last 20 messages)
 */

import makeWASocket, {
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  downloadMediaMessage,
  DisconnectReason,
} from '@whiskeysockets/baileys';
import { Boom } from '@hapi/boom';
import qrcode from 'qrcode-terminal';
import pino from 'pino';
import axios from 'axios';
import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';
import { homedir } from 'os';
import { randomBytes } from 'crypto';

// ── Configuration ─────────────────────────────────────────────────────────────
const ZERO_API_URL  = process.env.ZERO_API_URL  || 'http://localhost:18790/v1/chat/completions';
const ZERO_MODEL    = process.env.ZERO_MODEL    || 'openrouter/auto';
const SESSION_DIR   = join(process.cwd(), '.baileys_session');
const MEDIA_DIR     = join(homedir(), '.zero', 'whatsapp_media');
const MAX_HISTORY   = 20;

// ── In-memory conversation histories ─────────────────────────────────────────
const histories = new Map();   // Map<jid, {role, content}[]>

function getHistory(jid) {
  if (!histories.has(jid)) histories.set(jid, []);
  return histories.get(jid);
}

function pushHistory(jid, role, content) {
  const h = getHistory(jid);
  h.push({ role, content });
  if (h.length > MAX_HISTORY) h.splice(0, h.length - MAX_HISTORY);
}

// ── Zero API call ─────────────────────────────────────────────────────────────
async function askZero(jid, userText) {
  const messages = [
    ...getHistory(jid),
    { role: 'user', content: userText },
  ];

  try {
    const res = await axios.post(
      ZERO_API_URL,
      { model: ZERO_MODEL, messages, stream: false },
      { timeout: 120_000, headers: { 'Content-Type': 'application/json' } }
    );
    const reply = res.data?.choices?.[0]?.message?.content || '(no response)';
    pushHistory(jid, 'user',      userText);
    pushHistory(jid, 'assistant', reply);
    return reply;
  } catch (err) {
    const detail = err.response?.data ? JSON.stringify(err.response.data) : err.message;
    console.error(`[Zero API] Error: ${detail}`);
    return `⚠️ Zero is not responding right now. (${err.message})`;
  }
}

// ── Text extractor ────────────────────────────────────────────────────────────
function extractText(msg) {
  const m = msg.message;
  if (!m) return null;
  return (
    m.conversation                             ||
    m.extendedTextMessage?.text                ||
    m.imageMessage?.caption                    ||
    m.videoMessage?.caption                    ||
    m.documentMessage?.caption                 ||
    null
  );
}

// ── Voice note downloader ─────────────────────────────────────────────────────
async function downloadVoice(sock, msg) {
  try {
    await mkdir(MEDIA_DIR, { recursive: true });
    const buf  = await downloadMediaMessage(msg, 'buffer', {}, { reuploadRequest: sock.updateMediaMessage });
    const ext  = 'ogg';
    const name = `voice_${Date.now()}_${randomBytes(4).toString('hex')}.${ext}`;
    const dest = join(MEDIA_DIR, name);
    await writeFile(dest, buf);
    console.log(`[Voice] Saved → ${dest}`);
    return dest;
  } catch (err) {
    console.error(`[Voice] Download failed: ${err.message}`);
    return null;
  }
}

// ── Bridge ────────────────────────────────────────────────────────────────────
async function startBridge() {
  console.log('');
  console.log('╔══════════════════════════════════════╗');
  console.log('║   Zero — WhatsApp Bridge (Baileys)   ║');
  console.log('╚══════════════════════════════════════╝');
  console.log(`  API  : ${ZERO_API_URL}`);
  console.log(`  Auth : ${SESSION_DIR}`);
  console.log('');

  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
  const { version }          = await fetchLatestBaileysVersion();
  const logger               = pino({ level: 'silent' });

  console.log(`  Baileys version: ${version.join('.')}`);

  const sock = makeWASocket({
    version,
    logger,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    printQRInTerminal: false,       // we print ourselves
    browser: ['Zero', 'cli', '1.0.0'],
    syncFullHistory: false,
    markOnlineOnConnect: false,
  });

  // Suppress WebSocket-level noise
  if (sock.ws?.on) {
    sock.ws.on('error', (err) => console.error('[WS]', err.message));
  }

  // ── Connection updates ──────────────────────────────────────────────────
  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log('\n📱 Scan this QR code with WhatsApp:');
      console.log('   Settings → Linked Devices → Link a Device\n');
      qrcode.generate(qr, { small: true });
      console.log('\nWaiting for scan...\n');
    }

    if (connection === 'open') {
      const name = sock.user?.name || 'Unknown';
      const num  = sock.user?.id?.split(':')[0] || 'Unknown';
      console.log(`\n🟢 Connected as ${name} (+${num})\n`);
    }

    if (connection === 'close') {
      const code = (lastDisconnect?.error instanceof Boom)
        ? lastDisconnect.error.output.statusCode
        : undefined;
      const loggedOut = code === DisconnectReason.loggedOut;

      console.log(`🔴 Disconnected (status ${code ?? 'unknown'})`);

      if (loggedOut) {
        console.log('   Logged out — delete .baileys_session/ and restart to re-scan QR.');
      } else {
        console.log('   Reconnecting in 5 s...');
        setTimeout(startBridge, 5000);
      }
    }
  });

  // ── Persist credentials ─────────────────────────────────────────────────
  sock.ev.on('creds.update', saveCreds);

  // ── Incoming messages ───────────────────────────────────────────────────
  sock.ev.on('messages.upsert', async ({ messages: msgs, type }) => {
    if (type !== 'notify') return;

    for (const msg of msgs) {
      if (msg.key.fromMe) continue;
      if (msg.key.remoteJid === 'status@broadcast') continue;

      const jid = msg.key.remoteJid;   // full JID — used for replies
      let userText = extractText(msg) || '';
      const isVoice = !!(msg.message?.audioMessage?.pttSeconds);

      // ── Voice note ────────────────────────────────────────────────────
      if (isVoice || msg.message?.audioMessage) {
        console.log(`[Voice] Received from ${jid}`);
        const voicePath = await downloadVoice(sock, msg);
        userText = voicePath
          ? `[Voice Note — audio saved at: ${voicePath}]. Please acknowledge receipt.`
          : '[Voice Note received — could not download audio]';
      }

      // ── Other media (image/video/doc) with no caption ─────────────────
      if (!userText) {
        const m = msg.message || {};
        if      (m.imageMessage)    userText = '[Image received]';
        else if (m.videoMessage)    userText = '[Video received]';
        else if (m.documentMessage) userText = '[Document received]';
        else                        continue;  // skip truly empty messages
      }

      const ts   = new Date().toLocaleTimeString();
      const from = jid.split('@')[0];
      console.log(`[${ts}] ${from}: ${userText.slice(0, 80)}${userText.length > 80 ? '…' : ''}`);

      // ── Ask Zero ──────────────────────────────────────────────────────
      const reply = await askZero(jid, userText);
      await sock.sendMessage(jid, { text: reply });
      console.log(`[${ts}] Zero → ${from}: ${reply.slice(0, 80)}${reply.length > 80 ? '…' : ''}`);
    }
  });

  return sock;
}

// ── Entry point ───────────────────────────────────────────────────────────────
startBridge().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});

process.on('SIGINT',  () => { console.log('\nShutting down.'); process.exit(0); });
process.on('SIGTERM', () => { process.exit(0); });
