const assert=require('node:assert/strict'),{identity,matchData}=require('../zonaok-acta-fitxa.js');
const id=identity('https://www.hoqueipatins.fecapa.cat/?liga=4786&partido=152375');
assert.equal(id.key,'4786|152375');assert.equal(identity('https://example.com/?liga=4786&partido=152375'),null);
const row={home:'A',away:'B',homeScore:0,awayScore:0};
const master={source:'FECAPA',players:{p:{name:'Jugador prova'}},matchAppearances:{a:{leagueId:'4786',matchId:'152375',playerId:'p',side:'home',stats:{goals:0}},b:{leagueId:'4786',matchId:'152376',playerId:'p',side:'away'}}};
const state={matches:{[id.key]:{status:'verified',details:{source:'FECAPA',fouls:{home:0,away:7}}}}};
const a=matchData(id,row,null,master,state);assert.equal(a.sides.home.length,1);assert.equal(a.sides.away.length,0);assert.equal(a.details.fouls.home,0);assert.equal(a.details.fouls.away,7);assert.equal(matchData(id,row,null,null,null).details.fouls,undefined);console.log('Fitxa pròpia: identificació, jugadors i faltes correctes');
