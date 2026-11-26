const assert=require('node:assert/strict');const {summarize}=require('../zonaok-actualitzacions.js');
const stamp='2026-11-25T20:00:00Z';
const doc={season:'2026/2027',updatedAt:stamp,sources:{agenda:{capturedAt:'2026-11-25T13:00:00Z'},directe:{capturedAt:stamp}},matches:[
{competition:'JUVENIL OR 6',homeScore:0,awayScore:0,actaUrl:'link',actaState:'available'},
{competition:'JUVENIL OR 8',homeScore:2,awayScore:1,actaUrl:'link',actaState:'pending'},
{competition:'INFANTIL OR 10',homeScore:null,awayScore:null}]};
const s=summarize(doc,{capturedAt:stamp,competitions:{}},{updatedAt:stamp,players:{a:{}},memberships:{a:{}},matchAppearances:{}});
assert.equal(s.total,3);assert.equal(s.results,2);assert.equal(s.verified,1);assert.equal(s.links,2);assert.equal(s.pending,1);assert.equal(s.categories.length,2);assert.equal(s.categories.find(c=>c.name==='JUVENIL OR').total,2);assert.equal(s.sources.agenda,'2026-11-25T13:00:00Z');assert.equal(s.sources.actes,null);assert.equal(s.players,1);assert.equal(summarize(null,null,null).total,null);
assert.equal(s.identified,2);
const ids=summarize({matches:[
 {competition:'ALEVÍ OR 1',matchId:'12345',homeScore:1,awayScore:2},
 {competition:'ALEVÍ OR 1',idp:23456},
 {competition:'ALEVÍ OR 2',id:'34567',actaUrl:'https://www.hoqueipatins.fecapa.cat/?liga=4789&partido=34567',actaState:'available'},
 {competition:'ALEVÍ OR 2',actaUrl:'https://www.hoqueipatins.fecapa.cat/?liga=4789&partido=45678'},
 {competition:'ALEVÍ OR 2',matchId:'',idp:0,actaUrl:' '},
 {competition:'ALEVÍ OR 2',matchId:'invalid',leagueId:'4789'}
]});
assert.equal(ids.identified,4);assert.equal(ids.links,2);assert.equal(ids.verified,1);
assert.equal(ids.categories[0].identified,4);assert.deepEqual(ids.categories[0].groups.map(g=>g.identified),[2,2]);
assert.equal(summarize(null,null,null).identified,null);
console.log('Proves resum correctes');
