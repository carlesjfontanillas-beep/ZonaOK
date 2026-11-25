const assert=require('node:assert/strict');
const {rowsInPeriod}=require('../zonaok-resultats-7dies.js');
const row=(iso,time,status='',competition='INFANTIL OR 10')=>({iso,time,status,competition,home:'A',away:'B'});
const now=new Date('2026-11-25T20:37:00Z'); // 21:37 a Madrid
const rows=[row('2026-11-25','21:37'),row('2026-11-25','21:38'),row('2026-11-23','22:00'),row('2026-11-18','21:37'),row('2026-11-18','21:36'),row('2026-12-02','21:37'),row('2026-12-02','21:38'),row('2026-11-26','09:00'),row('2026-11-26','08:00','AJORNAT'),row('2026-11-25','21:30','EN JOC')];
assert.deepEqual(rowsInPeriod(rows,'past',now).map(r=>r.iso+' '+r.time),['2026-11-25 21:37','2026-11-23 22:00','2026-11-18 21:37']);
assert.deepEqual(rowsInPeriod(rows,'upcoming',now).map(r=>r.iso+' '+r.time),['2026-11-25 21:38','2026-11-26 09:00','2026-12-02 21:37']);
const dst=new Date('2026-10-24T18:00:00Z');assert.equal(rowsInPeriod([row('2026-10-31','20:00'),row('2026-10-31','20:01')],'upcoming',dst).length,1);
assert.equal(rowsInPeriod([], 'upcoming',now).length,0);
console.log('Proves dels dos períodes de set dies superades');
