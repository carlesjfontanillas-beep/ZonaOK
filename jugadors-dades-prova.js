/* Exclusivament dades sintètiques. Mai fetch a ZonaOK-Dades ni credencials. */
(()=>{
'use strict';
const P='zonaok.jugadors.preview.v1', N=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim();
const players=[
 {playerId:'990000001',name:'Jugador de mostra A',birthYear:2014},
 {playerId:'990000002',name:'Jugadora de mostra B',birthYear:2014},
 {playerId:'990000003',name:'Porter de mostra C',birthYear:2013},
 {playerId:'990000004',name:'Jugador de mostra D',birthYear:2011},
 {playerId:'990000005',name:'Jugadora de mostra E',birthYear:2014}
];
const M=(id,team,club,league,group,filter,number,position,played,goals,assists,blueCards)=>({playerId:id,teamName:team,clubName:club,leagueId:league,leagueName:group.split(' OR ')[0]+' OR',groupName:group,teamFilterId:filter,seasonId:'41',seasonName:'2026/27',position,sports:{number,played,goals,assists,blueCards}});
const memberships=[
 M('990000001','FC BARCELONA','FC Barcelona','4789','ALEVI OR 3','99001',7,'field',12,24,8,1),
 M('990000001','FC BARCELONA','FC Barcelona','4786','INFANTIL OR 10','99002',7,'field',3,2,1,0),
 M('990000002','FC BARCELONA','FC Barcelona','4789','ALEVI OR 3','99001',9,'field',12,14,6,0),
 M('990000003','CP SANT CELONI B','CP Sant Celoni','4786','INFANTIL OR 10','99003',1,'goalkeeper',10,0,0,1),
 M('990000004','CP SANT CELONI B','CP Sant Celoni','4784','JUVENIL OR 6','99004',4,'field',9,15,3,2),
 M('990000005','CLUB DE MOSTRA','Club de mostra','4789','ALEVI OR 3','99005',8,'field',12,18,5,0)
];
const appearances=[{id:'990000001',date:'2026-11-22',rival:'Equip de mostra X',result:'5 : 2',g:2,a:1,c:true},{id:'990000001',date:'2026-11-15',rival:'Equip de mostra Y',result:'4 : 3',g:3,a:0,c:false},{id:'990000001',date:'2026-11-08',rival:'Equip de mostra Z',result:'6 : 1',g:2,a:1,c:true},{id:'990000003',date:'2026-11-22',rival:'Equip de mostra X',result:'2 : 2',g:0,a:0,c:false}].map((x,i)=>({playerId:x.id,matchId:String(999000+i),leagueId:x.id==='990000003'?'4786':'4789',teamFilterId:x.id==='990000003'?'99003':'99001',seasonId:'41',side:'home',teamName:x.id==='990000003'?'CP SANT CELONI B':'FC BARCELONA',shirtNumber:x.id==='990000003'?1:7,position:x.id==='990000003'?'goalkeeper':'field',captain:x.c,participation:'played',stats:{goals:x.g,assists:x.a},fixture:{date:x.date,rival:x.rival,result:x.result}}));
function read(){try{const v=JSON.parse(localStorage.getItem(P)||'{}');return {favorites:Array.isArray(v.favorites)?v.favorites.filter(x=>players.some(p=>p.playerId===x)):[],teamPlayers:v.teamPlayers&&typeof v.teamPlayers==='object'?v.teamPlayers:{}}}catch{return {favorites:[],teamPlayers:{}}}}
function write(v){localStorage.setItem(P,JSON.stringify(v));window.dispatchEvent(new Event('zonaok:jugadors-preferences'))}
function fav(id,on){const s=read();s.favorites=on?[...new Set([...s.favorites,id])]:s.favorites.filter(x=>x!==id);write(s)}
function assign(team,id){const s=read();if(id){s.teamPlayers[team]=id;s.favorites=[...new Set([...s.favorites,id])]}else delete s.teamPlayers[team];write(s)}
function list(id){return memberships.filter(m=>m.playerId===id)}
function teamMatches(m,teamId){const [,team,group]=String(teamId).split('|');if(!team||!group)return false;const a=N(m.teamName),b=N(team),g=N(group);const alias=(x)=>/^(BAR|BARCA|FC BARCELONA|FCB)( A)?$/.test(x)?'BARCA':/^(CPSCB|CPSC B|CP SANT CELONI B|SANT CELONI B)$/.test(x)?'CELONI B':x;return alias(a)===alias(b)&&N(m.groupName)===g}
window.ZonaOKJugadorsDemo=Object.freeze({players,memberships,appearances,norm:N,read,write,fav,assign,list,teamMatches});
})();
