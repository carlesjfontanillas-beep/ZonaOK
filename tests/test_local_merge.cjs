/* Regressions Safari localStorage: an Agenda import must not erase live scores. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/../index.html','utf8');
const safe=html.match(/<script id="zonaok-safe-store-v23">([\s\S]*?)<\/script>/)[1];
const map=new Map();
const storage={getItem:k=>map.has(k)?map.get(k):null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};
const window={localStorage:storage};
const ctx={window,localStorage:storage};vm.runInNewContext(safe,ctx);const api=window.ZonaOKSafeStorage;
const KEY='ZONAOK_FECAPA_SAFARI_V2';
const fixture={id:'A',iso:'2026-11-19',time:'18:00',home:'Barça Aleví',away:'Rival',competition:'ALEVÍ OR 3',homeScore:null,awayScore:null,venue:'Pista A',capturedAt:'2026-11-19T10:00:00Z'};
api.commit({agenda:{capturedAt:'2026-11-19T10:00:00Z',rows:[fixture]}});
let s=api.read();assert.equal(s.agenda.rows.length,1);
api.commit({agenda:{capturedAt:'2026-11-19T11:00:00Z',rows:[{...fixture,homeScore:1,awayScore:0,scoreCapturedAt:'2026-11-19T11:00:00Z',scoreSource:'En directe',capturedAt:'2026-11-19T11:00:00Z'}]}});
s=api.read();assert.equal(s.agenda.rows[0].homeScore,1);assert.equal(s.agenda.rows[0].awayScore,0);assert.equal(s.agenda.rows[0].scoreSource,'En directe');
// A newer imported schedule has old 0-0 scoreboard; must not override direct verified score.
api.commit({agenda:{capturedAt:'2026-11-19T16:00:00Z',rows:[{...fixture,homeScore:0,awayScore:0,capturedAt:'2026-11-19T16:00:00Z'}]}});
s=api.read();assert.equal(s.agenda.rows[0].homeScore,1);assert.equal(s.agenda.rows[0].awayScore,0);assert.equal(s.agenda.rows[0].scoreCapturedAt,'2026-11-19T11:00:00Z');
// An empty result cannot delete the confirmed scoreboard either.
api.commit({agenda:{rows:[{...fixture,homeScore:null,awayScore:null,capturedAt:'2026-11-20T12:00:00Z'}]}});
s=api.read();assert.equal(s.agenda.rows[0].homeScore,1);assert.equal(s.agenda.rows[0].awayScore,0);
// Direct with newer explicit score can update the game.
api.commit({agenda:{capturedAt:'2026-11-20T13:00:00Z',rows:[{...fixture,homeScore:3,awayScore:2,scoreCapturedAt:'2026-11-20T13:00:00Z',scoreSource:'En directe',capturedAt:'2026-11-20T13:00:00Z'}]}});
s=api.read();assert.equal(s.agenda.rows[0].homeScore,3);assert.equal(s.agenda.rows[0].awayScore,2);
// Older confirmed live update cannot go backwards.
api.commit({agenda:{rows:[{...fixture,homeScore:1,awayScore:0,scoreCapturedAt:'2026-11-20T11:00:00Z',capturedAt:'2026-11-20T14:00:00Z'}]}});
s=api.read();assert.equal(s.agenda.rows[0].homeScore,3);
// Unrelated standings/actas must survive a score import and independent classification.
api.commit({'4786':{standings:[{team:'Sant Celoni',points:'6'}],standingsAt:'2026-11-19T10:00:00Z'},actaIndex:{'4789':{rows:[{id:'A',home:'Barça Aleví',away:'Rival',iso:'2026-11-19'}]}}});
api.commit({'4789':{standings:[{team:'Barça',points:'4'}],standingsAt:'2026-11-20T15:00:00Z'}});
s=api.read();assert.equal(s['4786'].standings[0].points,'6');assert.equal(s.actaIndex['4789'].rows.length,1);
assert.equal(s['4789'].standings[0].points,'4');
console.log('7 validations: local storage score merge, old/empty agenda, newer/stale live, standings, actes OK');
