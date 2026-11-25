const encoder = new TextEncoder();
const TOKEN_BYTES = 32;
const BODY_LIMIT = 16 * 1024;
const TEST_COOLDOWN_MS = 30_000;

function response(body, status, origin, extra = {}) {
  const headers = new Headers({
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    ...extra,
  });
  if (origin) {
    headers.set("access-control-allow-origin", origin);
    headers.set("vary", "Origin");
    headers.set("access-control-allow-methods", "GET, POST, OPTIONS");
    headers.set("access-control-allow-headers", "Content-Type, Authorization");
    headers.set("access-control-max-age", "600");
  }
  return new Response(JSON.stringify(body), { status, headers });
}

function b64url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromB64url(value) {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) throw new Error("bad base64url");
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
}

function concat(...parts) {
  const size = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) { out.set(part, offset); offset += part.length; }
  return out;
}

async function sha256(value) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", typeof value === "string" ? encoder.encode(value) : value));
}

async function randomToken() {
  return b64url(crypto.getRandomValues(new Uint8Array(TOKEN_BYTES)));
}

async function readJson(request) {
  const length = Number(request.headers.get("content-length") || 0);
  if (length > BODY_LIMIT) throw new Error("too large");
  const bytes = new Uint8Array(await request.arrayBuffer());
  if (bytes.length > BODY_LIMIT) throw new Error("too large");
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

function allowedPushEndpoint(raw) {
  let url;
  try { url = new URL(raw); } catch { return false; }
  if (url.protocol !== "https:" || url.username || url.password || url.port || url.hash) return false;
  const host = url.hostname.toLowerCase();
  return host === "fcm.googleapis.com" || host.endsWith(".push.apple.com") ||
    host === "push.services.mozilla.com" || host.endsWith(".push.services.mozilla.com") ||
    host === "updates.push.services.mozilla.com" || host.endsWith(".notify.windows.com");
}

function validateSubscription(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  if (!allowedPushEndpoint(value.endpoint)) return false;
  if (!value.keys || typeof value.keys !== "object") return false;
  try {
    const point = fromB64url(value.keys.p256dh);
    const auth = fromB64url(value.keys.auth);
    return point.length === 65 && point[0] === 4 && auth.length === 16;
  } catch { return false; }
}

function normalizePreferences(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const text = JSON.stringify(value);
  if (text.length > 2048) return null;
  return text;
}

async function authSubscription(request, env) {
  const match = /^Bearer ([A-Za-z0-9_-]{40,64})$/.exec(request.headers.get("authorization") || "");
  if (!match) return null;
  const tokenHash = b64url(await sha256(match[1]));
  return env.DB.prepare("SELECT id, endpoint, p256dh, auth, preferences_json, enabled, last_test_at FROM subscriptions WHERE token_hash = ? AND enabled = 1")
    .bind(tokenHash).first();
}

async function hmac(keyBytes, data) {
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, data));
}

async function hkdfExpand(prk, info, length) {
  let previous = new Uint8Array(0);
  const blocks = [];
  for (let counter = 1; blocks.reduce((n, item) => n + item.length, 0) < length; counter++) {
    previous = await hmac(prk, concat(previous, info, new Uint8Array([counter])));
    blocks.push(previous);
  }
  return concat(...blocks).slice(0, length);
}

async function vapidAuthorization(endpoint, env) {
  const publicKey = fromB64url(env.VAPID_PUBLIC_KEY);
  const privateKey = fromB64url(env.VAPID_PRIVATE_KEY);
  if (publicKey.length !== 65 || privateKey.length !== 32) throw new Error("invalid VAPID keys");
  const jwk = {
    kty: "EC", crv: "P-256", x: b64url(publicKey.slice(1, 33)), y: b64url(publicKey.slice(33)),
    d: b64url(privateKey), ext: true, key_ops: ["sign"],
  };
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const audience = new URL(endpoint).origin;
  const now = Math.floor(Date.now() / 1000);
  const header = b64url(encoder.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const payload = b64url(encoder.encode(JSON.stringify({ aud: audience, exp: now + 3600, sub: env.VAPID_SUBJECT })));
  const input = `${header}.${payload}`;
  const signature = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, encoder.encode(input)));
  return `vapid t=${input}.${b64url(signature)}, k=${env.VAPID_PUBLIC_KEY}`;
}

async function encryptPush(subscription, payload) {
  const uaPublicBytes = fromB64url(subscription.p256dh);
  const authSecret = fromB64url(subscription.auth);
  const uaPublic = await crypto.subtle.importKey("raw", uaPublicBytes, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const ephemeral = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const asPublic = new Uint8Array(await crypto.subtle.exportKey("raw", ephemeral.publicKey));
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaPublic }, ephemeral.privateKey, 256));

  // RFC 8291 §3.3: ECDH secret as IKM, auth secret as HKDF salt.
  const authKey = await crypto.subtle.importKey("raw", shared, { name: "HKDF" }, false, ["deriveBits"]);
  const context = concat(encoder.encode("WebPush: info\0"), uaPublicBytes, asPublic);
  const ikm = new Uint8Array(await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt: authSecret, info: context }, authKey, 256));
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const prk = await hmac(salt, ikm);
  const cek = await hkdfExpand(prk, encoder.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdfExpand(prk, encoder.encode("Content-Encoding: nonce\0"), 12);

  const plaintext = concat(encoder.encode(payload), new Uint8Array([2]));
  if (plaintext.length > 3993) throw new Error("push payload too large");
  const padded = new Uint8Array(3993);
  padded.set(plaintext);
  const aesKey = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, tagLength: 128 }, aesKey, padded));
  const rs = new Uint8Array([0, 0, 16, 0]);
  return concat(salt, rs, new Uint8Array([asPublic.length]), asPublic, ciphertext);
}

async function sendPush(subscription, message, env) {
  const body = await encryptPush(subscription, JSON.stringify(message));
  const authorization = await vapidAuthorization(subscription.endpoint, env);
  return fetch(subscription.endpoint, {
    method: "POST", redirect: "manual", body,
    headers: {
      Authorization: authorization,
      "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream",
      TTL: "60",
      Urgency: "normal",
    },
  });
}

async function handle(request, env) {
  const url = new URL(request.url);
  const origin = request.headers.get("origin");
  const allowedOrigin = env.ALLOWED_ORIGIN || "https://carlesjfontanillas-beep.github.io";
  if (origin && origin !== allowedOrigin) return response({ error: "origin_not_allowed" }, 403);
  if (request.method === "OPTIONS") {
    if (origin !== allowedOrigin) return response({ error: "origin_not_allowed" }, 403);
    return new Response(null, { status: 204, headers: {
      "access-control-allow-origin": allowedOrigin,
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "Content-Type, Authorization",
      "access-control-max-age": "600", vary: "Origin",
    } });
  }
  if (url.pathname === "/health" && request.method === "GET") {
    return response({ ok: true, service: "zonaok-push", database: Boolean(env.DB), vapid: Boolean(env.VAPID_PRIVATE_KEY && env.VAPID_PUBLIC_KEY), sportsDelivery: false }, 200, origin === allowedOrigin ? allowedOrigin : null);
  }
  if (request.method !== "POST") return response({ error: "not_found" }, 404, origin === allowedOrigin ? allowedOrigin : null);
  if (origin !== allowedOrigin) return response({ error: "origin_required" }, 403);
  if (!env.DB) return response({ error: "database_unavailable" }, 503, allowedOrigin);
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) return response({ error: "json_required" }, 415, allowedOrigin);

  try {
    if (url.pathname === "/subscriptions") {
      const input = await readJson(request);
      if (!validateSubscription(input.subscription)) return response({ error: "invalid_subscription" }, 400, allowedOrigin);
      const preferences = normalizePreferences(input.preferences || {});
      if (preferences === null) return response({ error: "invalid_preferences" }, 400, allowedOrigin);
      const endpoint = input.subscription.endpoint;
      const existing = await env.DB.prepare("SELECT id, token_hash, p256dh, auth FROM subscriptions WHERE endpoint = ?").bind(endpoint).first();
      if (existing) {
        const auth = /^Bearer ([A-Za-z0-9_-]{40,64})$/.exec(request.headers.get("authorization") || "");
        const tokenMatches = auth && b64url(await sha256(auth[1])) === existing.token_hash;
        const subscriptionKeysMatch = input.subscription.keys.p256dh === existing.p256dh && input.subscription.keys.auth === existing.auth;
        // Recover a lost local bearer token only when the browser presents the exact same Push subscription keys.
        if (!tokenMatches && !subscriptionKeysMatch) return response({ error: "subscription_exists" }, 409, allowedOrigin);
        const token = await randomToken();
        await env.DB.prepare("UPDATE subscriptions SET token_hash = ?, p256dh = ?, auth = ?, preferences_json = ?, enabled = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?")
          .bind(b64url(await sha256(token)), input.subscription.keys.p256dh, input.subscription.keys.auth, preferences, existing.id).run();
        return response({ token }, 200, allowedOrigin);
      }
      const ip = request.headers.get("cf-connecting-ip");
      if (!ip) return response({ error: "registration_rate_limited" }, 429, allowedOrigin);
      const day = new Date().toISOString().slice(0, 10);
      const ipHash = b64url(await sha256(`${day}:${ip}`));
      const allowed = await env.DB.prepare("INSERT INTO registration_limits (day_key, ip_hash, hits) VALUES (?, ?, 1) ON CONFLICT(day_key, ip_hash) DO UPDATE SET hits = hits + 1 WHERE hits < 5 RETURNING hits")
        .bind(day, ipHash).first();
      if (!allowed) return response({ error: "registration_rate_limited" }, 429, allowedOrigin, { "retry-after": "3600" });
      const id = crypto.randomUUID();
      const token = await randomToken();
      await env.DB.prepare("INSERT INTO subscriptions (id, token_hash, endpoint, p256dh, auth, preferences_json) VALUES (?, ?, ?, ?, ?, ?)")
        .bind(id, b64url(await sha256(token)), endpoint, input.subscription.keys.p256dh, input.subscription.keys.auth, preferences).run();
      return response({ token }, 201, allowedOrigin);
    }

    const subscription = await authSubscription(request, env);
    if (!subscription) return response({ error: "unauthorized" }, 401, allowedOrigin);
    if (url.pathname === "/preferences") {
      const input = await readJson(request);
      const preferences = normalizePreferences(input.preferences);
      if (preferences === null) return response({ error: "invalid_preferences" }, 400, allowedOrigin);
      await env.DB.prepare("UPDATE subscriptions SET preferences_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?").bind(preferences, subscription.id).run();
      return response({ ok: true }, 200, allowedOrigin);
    }
    if (url.pathname === "/unsubscribe") {
      await env.DB.prepare("DELETE FROM subscriptions WHERE id = ?").bind(subscription.id).run();
      return response({ ok: true }, 200, allowedOrigin);
    }
    if (url.pathname === "/test") {
      if (!env.VAPID_PRIVATE_KEY || !env.VAPID_PUBLIC_KEY || !env.VAPID_SUBJECT) return response({ error: "push_not_configured" }, 503, allowedOrigin);
      const last = Date.parse(subscription.last_test_at || "1970-01-01T00:00:00Z");
      if (Date.now() - last < TEST_COOLDOWN_MS) return response({ error: "test_rate_limited" }, 429, allowedOrigin, { "retry-after": "30" });
      const claim = await env.DB.prepare("UPDATE subscriptions SET last_test_at = CURRENT_TIMESTAMP WHERE id = ? AND (last_test_at IS NULL OR last_test_at <= datetime('now', '-30 seconds'))")
        .bind(subscription.id).run();
      if (!claim.meta?.changes) return response({ error: "test_rate_limited" }, 429, allowedOrigin, { "retry-after": "30" });
      const result = await sendPush(subscription, { title: "ZonaOK · prova", body: "La notificació de prova funciona en aquest dispositiu.", url: "/ZonaOK/", eventId: `test-${subscription.id}` }, env);
      if (result.status === 404 || result.status === 410) {
        await env.DB.prepare("UPDATE subscriptions SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?").bind(subscription.id).run();
        return response({ error: "subscription_expired" }, 410, allowedOrigin);
      }
      if (!result.ok) return response({ error: "push_service_rejected", status: result.status }, 502, allowedOrigin);
      return response({ ok: true }, 200, allowedOrigin);
    }
    return response({ error: "not_found" }, 404, allowedOrigin);
  } catch (error) {
    if (error?.message === "too large") return response({ error: "payload_too_large" }, 413, allowedOrigin);
    if (error instanceof SyntaxError || error instanceof TypeError) return response({ error: "invalid_request" }, 400, allowedOrigin);
    return response({ error: "internal_error" }, 500, allowedOrigin);
  }
}

export default {
  async fetch(request, env) {
    try { return await handle(request, env); }
    catch { return response({ error: "internal_error" }, 500); }
  },
};
