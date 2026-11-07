import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogMaps, mapFor, lightingStates} from '../public/atlas-model.js';

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
