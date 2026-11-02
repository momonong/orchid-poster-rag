const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createAppURL}=require('../orchid/static/urls.js');
for (const prefix of ['', '/orchid-poster']) test(`application URLs retain prefix ${prefix}`,()=>{
  const resolve=createAppURL(`https://orchid.test${prefix}/urls.js`);
  for(const value of ['/api/chat','/api/documents/poster#page=1','/assets/a.webp','/assets/tour-preview/audio/en.wav'])
    assert.equal(resolve(value),prefix+value);
  for(const value of ['https://example.org/paper','//example.org/paper','#overview','blob:fixture','./tour-data.json'])
    assert.equal(resolve(value),value);
  assert.equal(resolve(prefix+'/api/chat'),prefix+'/api/chat');
});
