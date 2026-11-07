import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogMaps, mapFor, lightingStates,hourFromTime,hourLabel,mapAtHour,clockFor,hourFromDialPoint} from '../public/atlas-model.js';

test('day/night selects distinct immutable image revisions on the same level', () => {
  const maps=catalogMaps({levels:[{level:0,revision:'day-pixels',variant:'day'},
    {level:0,revision:'night-pixels',variant:'night'}, {level:30,revision:'cave',variant:'fixed'}]});
  assert.equal(mapFor(maps,0,'night').revision,'night-pixels');
  assert.equal(mapFor(maps,0,'day').revision,'day-pixels');
  assert.deepEqual(lightingStates(maps,0),['day','night']);
  assert.equal(mapFor(maps,30,'night').revision,'cave');
  assert.deepEqual(lightingStates(maps,30),[]);
});

test('legacy catalogs remain usable without inventing a night variant', () => {
  const maps=catalogMaps({revision:'legacy',levels:[{level:1}]});
  assert.equal(mapFor(maps,1,'night').revision,'legacy');
  assert.deepEqual(lightingStates(maps,1),['day']);
  assert.equal(mapFor(maps,99,'night'),undefined);
});

test('grouped variants inherit shared geometry and resolve their own files', () => {
  const maps=catalogMaps({levels:[{level:5,width:4000,variants:[
    {variant:'day',revision:'r5day'}, {variant:'night',revision:'r5night'}]}]});
  assert.equal(mapFor(maps,5,'night').width,4000);
  assert.equal(mapFor(maps,5,'night').revision,'r5night');
});

test('hour clock reuses matching native lighting and never substitutes an unavailable twilight render',()=>{
 const clock={step_minutes:60,hours:Array.from({length:24},(_,hour)=>({hour,variant:hour===6||hour===18?'twilight':hour<6||hour>18?'night':'day'}))};
 const maps=catalogMaps({levels:[{level:0,clock,variants:[{variant:'day',revision:'day'},{variant:'night',revision:'night'}]},{level:30,variant:'fixed',revision:'cave'}]});
 assert.equal(mapAtHour(maps,0,15).revision,'day');assert.equal(mapAtHour(maps,0,23).revision,'night');
 assert.equal(mapAtHour(maps,0,6),undefined);assert.equal(mapAtHour(maps,30,6).revision,'cave');assert.equal(clockFor(maps,30),undefined);
 maps.push({...maps[0],variant:'twilight',revision:'native-twilight'});
 assert.equal(mapAtHour(maps,0,6).revision,'native-twilight');assert.equal(mapAtHour(maps,0,18).revision,'native-twilight');
});

test('clock labels preserve old links and reject unsupported minute precision',()=>{
 assert.equal(hourFromTime('day'),12);assert.equal(hourFromTime('night'),1);assert.equal(hourFromTime('23:00'),23);
 assert.equal(hourFromTime('06:30'),null);assert.equal(hourFromTime('24:00'),null);assert.equal(hourLabel(6),'06:00');
});

test('24-hour dial follows its hand through midnight and ignores the pivot',()=>{
 assert.equal(hourFromDialPoint(0,-1),0);assert.equal(hourFromDialPoint(1,0),6);
 assert.equal(hourFromDialPoint(0,1),12);assert.equal(hourFromDialPoint(-1,0),18);
 for(let hour=0;hour<24;hour++){const a=hour*Math.PI/12;assert.equal(hourFromDialPoint(Math.sin(a),-Math.cos(a)),hour)}
 assert.equal(hourFromDialPoint(-.01,-1),0);assert.equal(hourFromDialPoint(.01,-1),0);
 assert.equal(hourFromDialPoint(0,0),null);assert.equal(hourFromDialPoint(.01,.01),null);
});

test('edition query preserves old links and only opts into retail explicitly',async()=>{
 const {editionFromQuery}=await import('../public/atlas-model.js');
 assert.equal(editionFromQuery(null),'july');assert.equal(editionFromQuery('retail'),'retail');assert.equal(editionFromQuery('july'),'july');assert.equal(editionFromQuery('unknown'),'july');
});

test('switching edition crops keeps the same world point at the same screen pixel',async()=>{
 const {offsetForBounds}=await import('../public/atlas-model.js');
 const july=[-32256,3584,32768,33536],retail=[-30720,7168,1024,25600];
 const scale=.7,world=[-12000,15000],view={x:-321,y:-654};
 const next=offsetForBounds(view.x,view.y,scale,july,retail);
 assert.equal(Math.round(next.x+(world[0]-retail[0])*scale),Math.round(view.x+(world[0]-july[0])*scale));
 assert.equal(Math.round(next.y+(world[1]-retail[1])*scale),Math.round(view.y+(world[1]-july[1])*scale));
 assert.deepEqual(offsetForBounds(next.x,next.y,scale,retail,july),view);
});
