const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const model = require('../future-model.js');

test('B1 can lose first and gain over a longer horizon without erasing the loss', () => {
  const delta = h => model.value('B1','keep',{horizon:h,gamma:1})-model.value('B1','archive',{horizon:h,gamma:1});
  assert.equal(delta(1),-6);
  assert.equal(delta(2),-2);
  assert.equal(delta(3),2);
});
test('all leaf masses normalize and expectation agrees with the explicit weighted sum',()=>{
  for(const pA of [0,.2,.5,1]) for(const pB1 of [0,.7,1]) {
    const options={pA,pA1:.3,pB1,gamma:1,horizon:3};
    const w=model.weights(pA,.3,pB1);
    assert.ok(Math.abs(Object.values(w).reduce((a,b)=>a+b,0)-1)<1e-12);
    const expected=w.A1*9+w.A2*1+w.B1*3+w.B2*(-9);
    assert.ok(Math.abs(model.aggregate('keep',options)-expected)<1e-12);
  }
});
test('evidence-aware policy is allowed to remove the sign collision',()=>{
  for(const id of ['A1','A2','B1','B2']) {
    assert.ok(model.value(id,'keep',{policy:'qualified'})<model.value(id,'archive',{policy:'qualified'}));
  }
  const a=model.aggregate('keep',{pA:1})-model.aggregate('archive',{pA:1});
  const b=model.aggregate('keep',{pA:0})-model.aggregate('archive',{pA:0});
  assert.ok(a>0 && b<0);
});
test('future narrative and generated images exist for every case and leaf',()=>{
  const imageHashes = new Set();
  const checkImage = file => {
    const bytes=fs.readFileSync(file);
    assert.ok(bytes.length>1000);
    assert.equal(bytes.toString('ascii',8,12),'WEBP');
    imageHashes.add(createHash('sha256').update(bytes).digest('hex'));
  };
  for(const id of Object.keys(model.stories)) {
    for(const panel of ['A1','A2','B1','B2']) {
      assert.equal(model.stories[id][panel].length,4);
      assert.equal(model.archiveStories[id][panel].length,3);
      checkImage(path.join(__dirname,`../assets/${id}-future-${panel}.webp`));
    }
    for(const panel of ['resolve','probe','uncertain','delay']) {
      checkImage(path.join(__dirname,`../assets/${id}-evidence-${panel}.webp`));
    }
  }
  assert.equal(imageHashes.size,32,'Each branch must have its own scene, not a copied placeholder.');
});
