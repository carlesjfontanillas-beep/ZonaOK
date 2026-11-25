const assert=require('node:assert/strict'),{axis,action}=require('../zonaok-gestos.js');
assert.equal(axis(-60,5,true,true),'week');assert.equal(action('week',-60,5),'next');
assert.equal(action('week',60,5),'previous');assert.equal(axis(5,60,true,true),'pull');
assert.equal(action('pull',5,73),'refresh');assert.equal(action('pull',5,50),'');
assert.equal(axis(5,-60,true,true),'native');assert.equal(axis(5,60,true,false),'native');
assert.equal(axis(60,5,false,true),'native');assert.equal(axis(20,20,true,true),'');
assert.equal(axis(40,40,true,true),'native');assert.equal(action('week',60,70),'');
assert.equal(action('pull',80,75),'');console.log('13 proves de gestos correctes');
