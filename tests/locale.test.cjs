const {test} = require('node:test');
const assert = require('node:assert/strict');
const {initialLanguage} = require('../orchid/static/locale.js');

test('first visit and invalid preferences use English; only Traditional Chinese is restored',()=>{
  assert.equal(initialLanguage(null),'en');
  assert.equal(initialLanguage({getItem:()=>null}),'en');
  assert.equal(initialLanguage({getItem:()=>'zh-TW'}),'zh-TW');
  assert.equal(initialLanguage({getItem:()=>'zh-CN'}),'en');
  assert.equal(initialLanguage({getItem:()=>{throw new Error('blocked storage');}}),'en');
});
