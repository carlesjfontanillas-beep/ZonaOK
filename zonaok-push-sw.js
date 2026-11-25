/* ZonaOK Web Push · preparació. Sense memòria cau ni enviaments automàtics. */
'use strict';
self.addEventListener('push', event => {
  let data;
  try { data = event.data?.json(); } catch (_) { return; }
  if (!data || typeof data.title !== 'string' || !data.title.trim()) return;
  const scope = new URL(self.registration.scope);
  let url = scope.href;
  try {
    const candidate = new URL(data.url || './', scope);
    if (candidate.origin === scope.origin && candidate.pathname.startsWith(scope.pathname)) url = candidate.href;
  } catch (_) {}
  const options = {
    body: String(data.body || '').slice(0, 300),
    icon: new URL('icon-192.png', scope).href,
    data: { url }
  };
  if (typeof data.eventId === 'string' && data.eventId.length <= 200) options.tag = data.eventId;
  event.waitUntil(self.registration.showNotification(data.title.slice(0, 100), options));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil((async () => {
    const scope = new URL(self.registration.scope);
    let target = scope.href;
    try {
      const url = new URL(event.notification.data?.url || './', scope);
      if (url.origin === scope.origin && url.pathname.startsWith(scope.pathname)) target = url.href;
    } catch (_) {}
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find(client => client.url === target);
    if (existing) return existing.focus();
    return self.clients.openWindow(target);
  })());
});
