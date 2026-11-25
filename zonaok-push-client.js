/* ZonaOK · Web Push client. No automatic permission prompt or registration. */
const SW = './zonaok-push-sw.js';
const KEY = 'ZONAOK_PUSH_DEVICE_V1';
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
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (_) { return null; }
}
async function post(api, path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch(api + path, { method: 'POST', headers, body: JSON.stringify(body), cache: 'no-store', credentials: 'omit' });
  if (!response.ok) throw new Error('Servidor push: ' + response.status);
  return response.status === 204 ? null : response.json();
}
export function pushStatus() {
  return { supported: window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window,
    permission: 'Notification' in window ? Notification.permission : 'unsupported',
    configuredDevice: Boolean(device()?.token) };
}
/* Call directly from an explicit button click. Never call at page load. */
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
    localStorage.setItem(KEY, JSON.stringify({api, token: result.token}));
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
  const registration = await navigator.serviceWorker.getRegistration('./');
  const subscription = await registration?.pushManager.getSubscription();
  // Unsubscribe locally even when network removal fails; server must purge 404/410.
  if (subscription) await subscription.unsubscribe();
  if (current?.api === api && current.token) await post(api, '/unsubscribe', {}, current.token);
  localStorage.removeItem(KEY);
  return pushStatus();
}
export async function testPush(config) {
  const {api} = getConfig(config);
  const current = device();
  if (!current?.token || current.api !== api) throw new Error('Dispositiu no registrat.');
  return post(api, '/test', {}, current.token);
}
