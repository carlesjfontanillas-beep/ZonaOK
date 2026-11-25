/* ZonaOK · Web Push client. Preferences are server-backed per device. */
const SW = './zonaok-push-sw.js';
const KEY = 'ZONAOK_PUSH_DEVICE_V1';
let recoveredDevice = null;

function ensureSupport() {
  if (!window.isSecureContext || !('serviceWorker' in navigator) ||
      !('PushManager' in window) || !('Notification' in window)) {
    throw new Error('Web Push no està disponible. A l’iPhone, obre ZonaOK des de la pantalla d’inici.');
  }
}
function getConfig(config) {
  const api = new URL(config?.api || 'about:blank');
  if (api.protocol !== 'https:' || !config?.publicKey) throw new Error('El servidor push encara no està configurat.');
  return { api: api.href.replace(/\/$/, ''), publicKey: config.publicKey };
}
function keyBytes(key) {
  const raw = atob(key.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(key.length / 4) * 4, '='));
  return Uint8Array.from(raw, c => c.charCodeAt(0));
}
function device() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (saved?.token) return saved;
  } catch (_) {}
  return recoveredDevice;
}
function rememberDevice(api, token) {
  recoveredDevice = { api, token };
  try { localStorage.setItem(KEY, JSON.stringify(recoveredDevice)); } catch (_) {}
}
async function request(api, path, {method = 'POST', body, token} = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch(api + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store', credentials: 'omit'
  });
  if (!response.ok) {
    const error = new Error('Servidor push: ' + response.status);
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}
async function post(api, path, body, token) {
  return request(api, path, {method: 'POST', body, token});
}
export function pushStatus() {
  return {
    supported: window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window,
    permission: 'Notification' in window ? Notification.permission : 'unsupported',
    configuredDevice: Boolean(device()?.token)
  };
}

/* Recover this browser's server record from its existing Push subscription.
   This also handles iOS Safari/PWA storage separation and cleared localStorage. */
export async function restorePushPreferences(config) {
  if (!window.isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window)) return null;
  const {api} = getConfig(config);
  const registration = await navigator.serviceWorker.getRegistration(SW);
  const subscription = await registration?.pushManager.getSubscription();
  if (!subscription) return null;

  const current = device();
  if (current?.api === api && current.token) {
    try {
      const result = await request(api, '/preferences', {method: 'GET', token: current.token});
      return result?.preferences && typeof result.preferences === 'object' ? result.preferences : {};
    } catch (error) {
      if (error.status !== 401) throw error;
    }
  }

  // No local token (or an expired one): exact Push keys let the server safely
  // recover the device and return its saved preferences without overwriting them.
  const result = await post(api, '/subscriptions', {subscription: subscription.toJSON()}, current?.api === api ? current.token : null);
  if (!result || typeof result.token !== 'string' || !result.token) throw new Error('No s’ha pogut recuperar el registre d’aquest dispositiu.');
  rememberDevice(api, result.token);
  return result.preferences && typeof result.preferences === 'object' ? result.preferences : {};
}

/* Call directly from an explicit button click. Never requests permission at page load. */
export async function enablePush(config, preferences) {
  ensureSupport();
  const {api, publicKey} = getConfig(config);
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Permís de notificacions no concedit.');
  await navigator.serviceWorker.register(SW, {scope: './'});
  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  const created = !subscription;
  if (!subscription) subscription = await registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: keyBytes(publicKey)});
  try {
    const previous = device();
    const token = previous?.api === api ? previous.token : null;
    const result = await post(api, '/subscriptions', {subscription: subscription.toJSON(), preferences}, token);
    if (!result || typeof result.token !== 'string' || !result.token) throw new Error('Resposta de subscripció invàlida.');
    rememberDevice(api, result.token);
    return pushStatus();
  } catch (error) {
    if (created) await subscription.unsubscribe().catch(() => {});
    throw error;
  }
}
export async function syncPushPreferences(config, preferences) {
  const {api} = getConfig(config);
  const current = device();
  if (!current?.token || current.api !== api) throw new Error('Dispositiu no registrat.');
  return post(api, '/preferences', {preferences}, current.token);
}
export async function disablePush(config) {
  const {api} = getConfig(config);
  const current = device();
  const registration = await navigator.serviceWorker.getRegistration(SW);
  const subscription = await registration?.pushManager.getSubscription();
  if (current?.api === api && current.token) await post(api, '/unsubscribe', {}, current.token);
  if (subscription) await subscription.unsubscribe();
  try { localStorage.removeItem(KEY); } catch (_) {}
  recoveredDevice = null;
  return pushStatus();
}
export async function testPush(config) {
  const {api} = getConfig(config);
  const current = device();
  if (!current?.token || current.api !== api) throw new Error('Dispositiu no registrat.');
  return post(api, '/test', {}, current.token);
}
