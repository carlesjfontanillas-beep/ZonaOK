const fs=require('node:fs'),zlib=require('node:zlib');
const {totals,category}=require('../zonaok-player-totals.js');
const master=JSON.parse(zlib.gunzipSync(fs.readFileSync('imports/jugadors-master.json.gz')));
const memberships=new Map(),appearances=new Map();
for(const m of Object.values(master.memberships||{})){
 const r={...m,sports:{...m.sports,...m.profileStats}};
 if(!memberships.has(r.playerId))memberships.set(r.playerId,[]);
 memberships.get(r.playerId).push(r);
}
for(const a of Object.values(master.matchAppearances||{})){
 if(!appearances.has(a.playerId))appearances.set(a.playerId,[]);
 appearances.get(a.playerId).push(a);
}
let multi=0,partial=0;
for(const [id,ms] of memberships){
 if(new Set(ms.map(m=>category(m).key)).size===ms.length)continue;
 multi++;const result=totals(ms,ms,appearances.get(id)||[]);
 if(result.partial.includes('played')||result.partial.includes('goals'))partial++;
}
console.log(JSON.stringify({multiGroupPlayers:multi,partialPlayedOrGoals:partial}));
const id='70072',rows=memberships.get(id)||[],acts=appearances.get(id)||[];
if(rows.length){
 const summary={all:totals(rows,rows,acts),groups:rows.map(m=>({group:m.groupName,leagueId:m.leagueId,actCount:acts.filter(a=>a.leagueId===m.leagueId).length,source:m.sports,computed:totals([m],rows,acts)}))};
 console.log('CAS_DE_CONTROL',JSON.stringify(summary));
}else console.log('CAS_DE_CONTROL: no disponible');
