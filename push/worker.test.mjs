import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { DatabaseSync } from "node:sqlite";
import { test } from "node:test";
import worker from "./worker.js";

const ORIGIN = "https://carlesjfontanillas-beep.github.io";
const encoder = new TextEncoder();

function b64url(bytes) {
  return Buffer.from(bytes).toString("base64url");
}

class TestD1 {
  constructor() {
    this.db = new DatabaseSync(":memory:");
    this.db.exec(readFileSyncSchema);
  }

  prepare(sql) {
    let params = [];
    const database = this.db;
    return {
      bind(...values) { params = values; return this; },
      first() { return database.prepare(sql).get(...params) || null; },
      run() {
        const result = database.prepare(sql).run(...params);
        return { meta: { changes: Number(result.changes) } };
      },
    };
  }
}

const readFileSyncSchema = await readFile(new URL("./schema.sql", import.meta.url), "utf8");
const db = new TestD1();
const vapidPair = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
const vapidPublicBytes = new Uint8Array(await crypto.subtle.exportKey("raw", vapidPair.publicKey));
const vapidPrivateJwk = await crypto.subtle.exportKey("jwk", vapidPair.privateKey);
const env = {
  DB: db,
  ALLOWED_ORIGIN: ORIGIN,
  VAPID_PUBLIC_KEY: b64url(vapidPublicBytes),
  VAPID_PRIVATE_KEY: vapidPrivateJwk.d,
  VAPID_SUBJECT: "https://carlesjfontanillas-beep.github.io/ZonaOK/",
};

async function makeSubscription(endpoint = "https://fcm.googleapis.com/fcm/send/test") {
  const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const publicBytes = new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey));
  return {
    pair,
    value: {
      endpoint,
      expirationTime: null,
      keys: { p256dh: b64url(publicBytes), auth: b64url(crypto.getRandomValues(new Uint8Array(16))) },
    },
  };
}

function request(path, { method = "GET", body, token, origin = ORIGIN, ip = "203.0.113.15" } = {}) {
  const headers = new Headers();
  if (origin) headers.set("Origin", origin);
  if (ip) headers.set("CF-Connecting-IP", ip);
  if (body !== undefined) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return new Request(`https://zonaok-push.carles-j-fontanillas.workers.dev${path}`, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function json(response) { return response.json(); }

async function decryptPayload(rawBody, clientSubscription, clientPair) {
  const bytes = new Uint8Array(rawBody);
  const salt = bytes.slice(0, 16);
  const recordSize = new DataView(bytes.buffer, bytes.byteOffset + 16, 4).getUint32(0);
  const keyIdLength = bytes[20];
  const serverPublicBytes = bytes.slice(21, 21 + keyIdLength);
  assert.equal(recordSize, 4096);
  assert.equal(keyIdLength, 65);

  const serverPublic = await crypto.subtle.importKey("raw", serverPublicBytes, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: serverPublic }, clientPair.privateKey, 256));
  const clientPublic = Buffer.from(clientSubscription.keys.p256dh, "base64url");
  const auth = Buffer.from(clientSubscription.keys.auth, "base64url");
  const context = new Uint8Array([
    ...encoder.encode("WebPush: info\0"), ...clientPublic, ...serverPublicBytes,
  ]);
  const authKey = await crypto.subtle.importKey("raw", shared, { name: "HKDF" }, false, ["deriveBits"]);
  const ikm = new Uint8Array(await crypto.subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt: auth, info: context }, authKey, 256));
  const extractKey = await crypto.subtle.importKey("raw", salt, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const prkBytes = await crypto.subtle.sign("HMAC", extractKey, ikm);
  const prk = await crypto.subtle.importKey("raw", prkBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  async function expand(info, length) {
    let previous = new Uint8Array(0);
    const result = [];
    for (let i = 1; result.reduce((n, x) => n + x.length, 0) < length; i++) {
      previous = new Uint8Array(await crypto.subtle.sign("HMAC", prk, new Uint8Array([...previous, ...encoder.encode(info), i])));
      result.push(previous);
    }
    return new Uint8Array(result.flatMap((x) => [...x]).slice(0, length));
  }
  const cek = await expand("Content-Encoding: aes128gcm\0", 16);
  const nonce = await expand("Content-Encoding: nonce\0", 12);
  const aes = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["decrypt"]);
  const ciphertext = bytes.slice(21 + keyIdLength);
  const plain = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce, tagLength: 128 }, aes, ciphertext));
  const delimiter = plain.indexOf(2);
  assert.notEqual(delimiter, -1);
  return JSON.parse(new TextDecoder().decode(plain.slice(0, delimiter)));
}

test("health is honest about configured components and blocks other origins", async () => {
  const ok = await worker.fetch(request("/health"), env);
  assert.equal(ok.status, 200);
  assert.deepEqual(await json(ok), { ok: true, service: "zonaok-push", database: true, vapid: true, sportsDelivery: false });
  assert.equal((await worker.fetch(request("/health", { origin: "https://attacker.example" }), env)).status, 403);
  assert.equal((await worker.fetch(request("/health", { origin: null }), env)).status, 200);
});

test("registration, preference update, encrypted push test, cooldown and unsubscribe", async (t) => {
  const client = await makeSubscription();
  const registered = await worker.fetch(request("/subscriptions", { method: "POST", body: { subscription: client.value, preferences: { clubs: ["test"] } } }), env);
  assert.equal(registered.status, 201);
  assert.equal(registered.headers.get("access-control-allow-origin"), ORIGIN);
  const { token } = await json(registered);
  assert.match(token, /^[A-Za-z0-9_-]{43}$/);
  const stored = db.db.prepare("SELECT * FROM subscriptions").get();
  assert.notEqual(stored.token_hash, token);
  assert.equal(stored.endpoint, client.value.endpoint);

  assert.equal((await worker.fetch(request("/preferences", { method: "POST", body: { preferences: {} } }), env)).status, 401);
  const preferences = await worker.fetch(request("/preferences", { method: "POST", token, body: { preferences: { clubs: ["club-a"] } } }), env);
  assert.equal(preferences.status, 200);
  assert.equal(db.db.prepare("SELECT preferences_json FROM subscriptions").get().preferences_json, '{"clubs":["club-a"]}');

  const originalFetch = globalThis.fetch;
  let pushRequest;
  globalThis.fetch = async (url, init) => {
    pushRequest = { url: String(url), init };
    return new Response(null, { status: 201 });
  };
  t.after(() => { globalThis.fetch = originalFetch; });
  const pushed = await worker.fetch(request("/test", { method: "POST", token, body: {} }), env);
  assert.equal(pushed.status, 200);
  assert.equal(pushRequest.url, client.value.endpoint);
  assert.equal(pushRequest.init.redirect, "manual");
  assert.equal(pushRequest.init.headers["Content-Encoding"], "aes128gcm");
  const message = await decryptPayload(pushRequest.init.body, client.value, client.pair);
  assert.deepEqual(message, {
    title: "ZonaOK · prova",
    body: "La notificació de prova funciona en aquest dispositiu.",
    url: "/ZonaOK/",
    eventId: `test-${stored.id}`,
  });
  const authHeader = /^vapid t=(.+), k=(.+)$/.exec(pushRequest.init.headers.Authorization);
  assert.ok(authHeader);
  const [, jwt, keyParam] = authHeader;
  assert.equal(keyParam, env.VAPID_PUBLIC_KEY);
  const parts = jwt.split(".");
  assert.equal(JSON.parse(Buffer.from(parts[0], "base64url").toString()).alg, "ES256");
  const claims = JSON.parse(Buffer.from(parts[1], "base64url").toString());
  assert.equal(claims.aud, "https://fcm.googleapis.com");
  assert.equal(claims.sub, env.VAPID_SUBJECT);
  const publicJwk = await crypto.subtle.exportKey("jwk", vapidPair.publicKey);
  const verifyKey = await crypto.subtle.importKey("jwk", publicJwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
  const verified = await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, verifyKey, Buffer.from(parts[2], "base64url"), encoder.encode(`${parts[0]}.${parts[1]}`));
  assert.equal(verified, true);

  assert.equal((await worker.fetch(request("/test", { method: "POST", token, body: {} }), env)).status, 429);
  assert.equal((await worker.fetch(request("/unsubscribe", { method: "POST", token, body: {} }), env)).status, 200);
  assert.equal(db.db.prepare("SELECT count(*) AS count FROM subscriptions").get().count, 0);
  assert.equal((await worker.fetch(request("/test", { method: "POST", token, body: {} }), env)).status, 401);
});


test("registration safely restores a lost local token only for the identical subscription keys", async () => {
  const client = await makeSubscription();
  const registered = await worker.fetch(request("/subscriptions", { method: "POST", body: { subscription: client.value } }), env);
  assert.equal(registered.status, 201);
  const { token: originalToken } = await json(registered);
  const originalHash = db.db.prepare("SELECT token_hash FROM subscriptions WHERE endpoint = ?").get(client.value.endpoint).token_hash;

  const mismatched = structuredClone(client.value);
  mismatched.keys.auth = b64url(crypto.getRandomValues(new Uint8Array(16)));
  const rejected = await worker.fetch(request("/subscriptions", { method: "POST", body: { subscription: mismatched } }), env);
  assert.equal(rejected.status, 409);
  assert.equal(db.db.prepare("SELECT token_hash FROM subscriptions WHERE endpoint = ?").get(client.value.endpoint).token_hash, originalHash);

  const recovered = await worker.fetch(request("/subscriptions", { method: "POST", body: { subscription: client.value } }), env);
  assert.equal(recovered.status, 200);
  const { token: recoveredToken } = await json(recovered);
  assert.notEqual(recoveredToken, originalToken);
  assert.equal((await worker.fetch(request("/preferences", { method: "POST", token: originalToken, body: { preferences: {} } }), env)).status, 401);
  assert.equal((await worker.fetch(request("/preferences", { method: "POST", token: recoveredToken, body: { preferences: {} } }), env)).status, 200);
});

test("registration rejects unsafe endpoints and limits new devices", async () => {
  const unsafe = await makeSubscription("https://169.254.169.254/latest/meta-data/");
  const blocked = await worker.fetch(request("/subscriptions", { method: "POST", body: { subscription: unsafe.value } }), env);
  assert.equal(blocked.status, 400);

  for (let i = 0; i < 5; i++) {
    const client = await makeSubscription(`https://fcm.googleapis.com/fcm/send/test-${i}`);
    const result = await worker.fetch(request("/subscriptions", { method: "POST", body: { subscription: client.value }, ip: "198.51.100.21" }), env);
    assert.equal(result.status, 201);
  }
  const sixth = await makeSubscription("https://fcm.googleapis.com/fcm/send/test-6");
  const limited = await worker.fetch(request("/subscriptions", { method: "POST", body: { subscription: sixth.value }, ip: "198.51.100.21" }), env);
  assert.equal(limited.status, 429);
});
