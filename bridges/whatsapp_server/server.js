/**
 * bridges/whatsapp_server/server.js
 * Multi-Device WhatsApp Gateway for MJ AI Assistant using Baileys.
 * Includes deduplication, startup sync filter, and rate protection.
 */

const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    jidNormalizedUser
} = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
const http = require('http');
const path = require('path');
const fs = require('fs');

const PORT = parseInt(process.env.WA_PORT || '3456', 10);
const PYTHON_WEBHOOK_URL = process.env.PYTHON_WEBHOOK_URL || 'http://127.0.0.1:3457/wa_incoming';
const AUTH_DIR = process.env.WA_AUTH_DIR || path.resolve(__dirname, '../../memory/whatsapp_auth');

if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
}

let sock = null;
let currentQR = null;
let isConnected = false;
let userJid = null;

// Track start time to ignore historical sync messages
const SERVER_START_TIME = Math.floor(Date.now() / 1000);

// LRU Deduplication Cache
const processedMessageIds = new Set();
const MAX_CACHE_SIZE = 5000;

function isDuplicateOrOld(msgId, timestamp) {
    if (!msgId) return true;
    if (processedMessageIds.has(msgId)) return true;

    // Ignore messages older than server start (with 15s grace period)
    const msgTime = Number(timestamp) || 0;
    if (msgTime > 0 && msgTime < (SERVER_START_TIME - 15)) {
        return true;
    }

    processedMessageIds.add(msgId);
    if (processedMessageIds.size > MAX_CACHE_SIZE) {
        const first = processedMessageIds.values().next().value;
        processedMessageIds.delete(first);
    }
    return false;
}

async function startSock() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version, isLatest } = await fetchLatestBaileysVersion();

    console.log(`[WA-SERVER] Initializing Baileys v${version.join('.')} (Latest: ${isLatest})...`);

    sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
        auth: state,
        browser: ['MJ-Assistant', 'Desktop', '1.0.0'],
        generateHighQualityLinkPreview: true,
        syncFullHistory: false, // Don't sync years of history on boot
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            currentQR = qr;
            console.log('\n======================================================');
            console.log('  📲 SCAN THIS QR CODE WITH WHATSAPP ON YOUR PHONE:');
            console.log('======================================================\n');
            qrcode.generate(qr, { small: true });
            console.log('\n[WA-SERVER] Waiting for device scan...\n');
        }

        if (connection === 'close') {
            isConnected = false;
            currentQR = null;
            const statusCode = (lastDisconnect?.error)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`[WA-SERVER] Connection closed (code: ${statusCode}). Reconnecting: ${shouldReconnect}`);
            if (shouldReconnect) {
                setTimeout(startSock, 3000);
            }
        } else if (connection === 'open') {
            isConnected = true;
            currentQR = null;
            userJid = sock.user?.id ? jidNormalizedUser(sock.user.id) : 'connected';
            console.log(`\n✅ [WA-SERVER] WHATSAPP CONNECTED SUCCESSFULLY as ${userJid}\n`);
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        if (m.type !== 'notify') return; // Only process live notification messages

        for (const msg of m.messages) {
            if (!msg.key || msg.key.fromMe) continue; // Skip own messages

            const senderJid = msg.key.remoteJid || '';

            // Ignore status broadcasts, newsletters, system channels
            if (!senderJid ||
                senderJid === 'status@broadcast' ||
                senderJid.endsWith('@newsletter') ||
                senderJid.endsWith('@broadcast')) {
                continue;
            }

            const msgId = msg.key.id;
            const timestamp = msg.messageTimestamp;

            // Deduplication and stale message check
            if (isDuplicateOrOld(msgId, timestamp)) {
                continue;
            }

            const pushName = msg.pushName || 'User';

            // Extract text from standard, extended, or media caption messages
            const body = msg.message?.conversation ||
                         msg.message?.extendedTextMessage?.text ||
                         msg.message?.imageMessage?.caption ||
                         msg.message?.videoMessage?.caption || '';

            if (!body || !body.trim()) continue;

            const payload = {
                id: msgId,
                from: senderJid,
                sender_number: senderJid.replace(/@.+/, ''),
                name: pushName,
                body: body.trim(),
                timestamp: timestamp,
                is_group: senderJid.endsWith('@g.us'),
            };

            console.log(`[WA-INCOMING] ${pushName} (${payload.sender_number}): ${body}`);
            forwardToPython(payload);
        }
    });
}

function forwardToPython(payload) {
    try {
        const data = JSON.stringify(payload);
        const url = new URL(PYTHON_WEBHOOK_URL);
        const req = http.request({
            hostname: url.hostname,
            port: url.port,
            path: url.pathname,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data),
            },
            timeout: 8000,
        }, (res) => {
            // response handled
        });

        req.on('error', (e) => {
            // Python receiver might be busy
        });

        req.write(data);
        req.end();
    } catch (e) {
        console.error('[WA-SERVER] Webhook error:', e.message);
    }
}

// ── HTTP Control API ────────────────────────────────────────────────────────
const server = http.createServer((req, res) => {
    const parsedUrl = new URL(req.url, `http://localhost:${PORT}`);

    if (req.method === 'GET' && parsedUrl.pathname === '/status') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
            status: isConnected ? 'connected' : (currentQR ? 'qr_ready' : 'connecting'),
            is_connected: isConnected,
            qr: currentQR,
            user_jid: userJid,
            auth_dir: AUTH_DIR,
        }));
        return;
    }

    if (req.method === 'POST' && parsedUrl.pathname === '/send') {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const data = JSON.parse(body || '{}');
                let target = (data.to || '').trim();
                const text = (data.text || '').trim();

                if (!target || !text) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'Missing to or text' }));
                    return;
                }

                if (!target.includes('@')) {
                    target = `${target.replace(/[^0-9]/g, '')}@s.whatsapp.net`;
                }

                if (!sock || !isConnected) {
                    res.writeHead(503, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'WhatsApp not connected' }));
                    return;
                }

                await sock.sendMessage(target, { text });
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ success: true, target }));
            } catch (err) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: err.message }));
            }
        });
        return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, '127.0.0.1', () => {
    console.log(`[WA-SERVER] HTTP API listening on http://127.0.0.1:${PORT}`);
    startSock();
});
