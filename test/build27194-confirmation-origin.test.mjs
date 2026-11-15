import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRuntime} from '../src/runtime.mjs';

const source=await readFile(new URL('../build/test-fixtures/overlay/webview/assets/async/486887.8844429c7e.js',import.meta.url),'utf8');
const runtime=createRuntime({store:{},randomUUID:()=> 'unused'});
globalThis.__codexComeBackLater=runtime;

test('paused-queue confirmation passes explicit human origin',()=>{
  const match=source.match(/canShow:"local"===sG&&l2\?\.type==="local"&&!dr&&p9,submit:(e=>void w4\(.*?\))\}\),/);
  assert.ok(match,'native dialog submission callback');
  let options;
  const confirm=new Function('w4','return ('+match[1]+')')(value=>{options=value;return 'native result';});
  for(const clear of [true,false]) {
    assert.equal(confirm(clear),undefined);
    assert.equal(runtime.isHuman(options),true,'user confirming submission must be tagged');
    assert.deepEqual(JSON.parse(JSON.stringify(options)),{clear,focusComposerAfterSubmit:true});
  }
});

test('goal-replacement confirmation passes explicit human origin',()=>{
  const match=source.match(/setIsSubmitting:d1,submit:(e=>w4\(.*?\))\}\);/);
  assert.ok(match,'native goal confirmation submission callback');
  let options;
  const original={skipGoalReplacementConfirmation:true,followUpSubmitAction:'queue'};
  const confirm=new Function('w4','return ('+match[1]+')')(value=>{options=value;return 'native result';});
  assert.equal(confirm(original),'native result');
  assert.equal(runtime.isHuman(options),true,'confirmed replacement must be tagged');
  assert.deepEqual(JSON.parse(JSON.stringify(options)),original);
});

for(const [name,extract,expected] of [
  ['keyboard', /stopRealtime:bb,submit:(e=>w4\(.*?\))[},]/, {draft:'text'}],
  ['submit control', /maybeSendQueuedSteerMessage:bM,submit:(e=>w4\(.*?\)),submitButtonMode:/, {draft:'text'}],
  ['dictation', /submitComposer:(e=>w4\(.*?\))[},]/, {draft:'text'}],
  ['editor', /rt=(e=>w4\(.*?\))[,;]/, {draft:'text',followUpGesture:'primary',focusComposerAfterSubmit:true}]
])test('explicit '+name+' passes human origin',()=>{
  const callback=source.match(extract)?.[1];
  assert.ok(callback,'generated '+name+' action');
  let options;
  const dispatch=new Function('w4','return ('+callback+')')(value=>{options=value;return 'result';});
  assert.equal(dispatch({draft:'text'}),'result');
  assert.equal(runtime.isHuman(options),true);
  assert.deepEqual(JSON.parse(JSON.stringify(options)),expected);
});
