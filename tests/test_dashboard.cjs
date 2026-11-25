const assert=require('node:assert/strict');const {summarize}=require('../zonaok-actualitzacions.js');
const stamp='2026-11-25T20:00:00Z';
const doc={season:'2026/2027',updatedAt:stamp,sources:{agenda:{capturedAt:'2026-11-25T13:00:00Z'},directe:{capturedAt:stamp}},matches:[
{competition:'JUVENIL OR 6',homeScore:0,awayScore:0,actaUrl:'link',actaState:'available'},
{competition:'JUVENIL OR 8',homeScore:2,awayScore:1,actaUrl:'link',actaState:'pending'},
{competition:'INFANTIL OR 10',homeScore:null,awayScore:null}]};
const s=summarize(doc,{capturedAt:stamp,competitions:{}},{updatedAt:stamp,players:{a:{}},memberships:{a:{}},matchAppearances:{}});
assert.equal(s.total,3);assert.equal(s.results,2);assert.equal(s.verified,1);assert.equal(s.links,2);assert.equal(s.pending,1);assert.equal(s.categories.length,2);assert.equal(s.categories.find(c=>c.name==='JUVENIL OR').total,2);assert.equal(s.sources.agenda,'2026-11-25T13:00:00Z');assert.equal(s.sources.actes,null);assert.equal(s.players,1);assert.equal(summarize(null,null,null).total,null);
console.log('Proves resum correctes');
