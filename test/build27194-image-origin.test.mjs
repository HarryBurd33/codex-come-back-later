// Review reproduction from the actual generated image-editor callback and wiring.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRuntime} from '../src/runtime.mjs';
import {transition} from '../src/state.mjs';
import {nativeRequire} from './build27194-path-fixture.mjs';

const source=await readFile(new URL('../build/test-fixtures/overlay/webview/assets/async/486887.8844429c7e.js',import.meta.url),'utf8');
const edit=source.match(/h\[5\]!==w\|\|h\[6\]!==p\?\(r=(async\(e,t\)=>\{.*?\}),h\[5\]=w/s);
const deps=source.match(/getSubmissionDependencies:(\(\)=>\(\{.*?\}\))\}\),c8=/s);
const composer=source.match(/oW=(e=>\{if\(globalThis\.__codexComeBackLater\.isHuman\(e\)\).*?\}),il\[587\]/s);
const capture=source.match(/cojq\(e,t,n\)\{(function __cblCapture\(scope,options\)\{.*?\})n.d/s);
assert.ok(edit&&deps&&composer&&capture,'pinned image submit, wiring and composer anchors');
assert.ok(source.includes('onImageEditSubmit:t=>k(e.id,t)'),'callback is an explicit image-editor submission');

const contextAttach=source.match(/el=(globalThis\.__codexComeBackLater\.attach\(el,V,\{accountId:e\.get\(P\.chatGptAuthenticatedAccountId\$\)\}\)),null!=V.additionalContextOverride/)?.[1];
assert.ok(contextAttach,'generated context attaches private ticket in dispatch scope');
const attachContext=new Function('el','V','e','P','return '+contextAttach);
function setup({uploadPending=true,missingMask=false}={}) {
  let record={generation:'original'},reads=0,submitted,queued;
  let account='account';
  const timers=[], values=new Map();
  const queue=nativeRequire({zTeN:{vP:(_,value)=>({value})},SPnB:{chatGptAuthenticatedAccountId$:'account',o8:'user'},
    Sd8U:{PR:{}},dWrR:{Q:()=>true}},['uIyc'],{setTimeout:(callback,ms)=>{assert.equal(ms,0);timers.push(callback);}})('uIyc');
  const attachmentScope={node:{},get:key=>key==='account'?account:key==='user'?'user':values.get(key)??key.value,
    set:(key,value)=>values.set(key,typeof value==='function'?value(values.get(key)??key.value):value)};
  const pending=uploadPending?queue.Mz(attachmentScope,{id:'mask-upload'}):undefined;
  const images=[{id:'image',src:'fixture-image'}];
  const runtime=createRuntime({store:{snapshot:()=>{reads++;return Promise.resolve(record);},
    read:async()=>record,change:async(_,command)=>{record=transition(record,command);}},
    randomUUID:()=> 'unused'});
  globalThis.__codexComeBackLater=runtime;
  const identity={accountId:'account',hostId:'host',threadId:'chat'};
  const followUp={type:'local',localConversationId:'chat'};
  const scope={get:(key,id)=>key==='account'?account:key==='followUp'?followUp:
    key==='manager'&&id==='chat'?'host':undefined};
  const prepare=new Function('a4','P','S','return '+capture[1])(
    {f:'followUp'},{chatGptAuthenticatedAccountId$:'account'},{qX:'manager'});
  const downstream=options=>{submitted=options;options?.onSubmitted?.();};
  queue.U_(attachmentScope,downstream);
  const w4=new Function('lL','l2','__cblCapture','dG','dz','sl','vp','wJ','w3',
    'return ('+composer[1]+')')(scope,followUp,prepare,null,null,'chat',false,downstream,
      {submit:(options,next)=>next(options)});
  const getDeps=new Function('gP','gT','w1','w4','lL','__cblCapture',
    'return '+deps[1])(()=>({addImageAttachment:()=>{}}),
      values=>{if(!missingMask)images.push({id:'mask',src:values[0].dataUrl});},
      (options,force)=>{
        assert.equal(force,true);
        if(!queue.lR(attachmentScope,options,force))return false;
        queued=options;
        return true;
      },w4,scope,prepare);
  const onImageEditSubmit=new Function('w','p','ok','mB','return '+edit[1])(
    getDeps,{get:()=>images},{gy:'images'},image=>image.id);
  return {runtime,identity,onImageEditSubmit,w4,scope,get record(){return record;},get reads(){return reads;},
    accept:receipt=>runtime.accepted(attachContext({},submitted,scope,{chatGptAuthenticatedAccountId$:'account'}),receipt,identity),
    markAgain:()=>{record={generation:'new'};},
    changeAccount:()=>{account='other';},
    settleUpload:outcome=>{
      if(outcome==='cancel')queue.TG(attachmentScope);
      if(outcome==='fail')pending.fail();
      else pending.succeed();
      for(const callback of timers.splice(0))callback();
    },
    get submitted(){return submitted;},get queued(){return queued;}};
}

test('accepted explicit image edit clears the marked chat',async()=>{
  const fixture=setup();
  assert.equal(await fixture.onImageEditSubmit('image',{prompt:'fixture edit'}),true);
  assert.equal(fixture.submitted.promptRawOverride,'fixture edit');
  assert.equal(fixture.reads,1,'direct composer must reuse the gesture ticket');
  await fixture.accept({status:'sent'});
  assert.equal(fixture.record,null,'image edit is a human prompt; confirmed acceptance must clear');
});

test('masked image edit captures a ticket before attachment deferral',async()=>{
  const fixture=setup();
  assert.equal(await fixture.onImageEditSubmit('image',{prompt:'fixture edit',maskSrc:'fixture-mask'}),true);
  assert.deepEqual(fixture.queued.firstTurnImageAttachmentIds,['image','mask']);
  assert.equal(fixture.submitted,undefined,'native attachment path deferred submission');
  assert.equal(fixture.reads,1,'capture must precede deferral so replay cannot adopt a newer mark');
  assert.equal(fixture.runtime.requiresReceipt(fixture.runtime.attach({},fixture.queued)),true);
  fixture.settleUpload('success');
  assert.equal(fixture.submitted,fixture.queued,'packaged replay retains the original options');
  assert.equal(fixture.reads,1);
  await fixture.accept({status:'sent'});
  assert.equal(fixture.record,null);
});

test('mask without pending upload submits directly with one gesture snapshot',async()=>{
  const fixture=setup({uploadPending:false});
  assert.equal(await fixture.onImageEditSubmit('image',{prompt:'edit',maskSrc:'mask-src'}),true);
  assert.equal(fixture.queued,undefined);
  assert.deepEqual(fixture.submitted.firstTurnImageAttachmentIds,['image','mask']);
  assert.equal(fixture.reads,1);
  await fixture.accept({status:'queued',serverAccepted:true});
  assert.equal(fixture.record,null);
});

for(const outcome of ['new mark','fail','cancel','account change','failed receipt']) {
  test('masked image replay preserves marker on '+outcome,async()=>{
    const fixture=setup();
    assert.equal(await fixture.onImageEditSubmit('image',{prompt:'edit',maskSrc:'mask-src'}),true);
    if(outcome==='new mark')fixture.markAgain();
    if(outcome==='account change')fixture.changeAccount();
    fixture.settleUpload(outcome);
    if(['new mark','failed receipt'].includes(outcome)) {
      assert.equal(fixture.submitted,fixture.queued);
      await fixture.accept(outcome==='new mark'?{status:'sent'}:{status:'failed'});
    } else assert.equal(fixture.submitted,undefined);
    assert.equal(fixture.reads,1);
    assert.equal(fixture.record.generation,outcome==='new mark'?'new':'original');
  });
}

test('unavailable mask retains native false result and does not submit',async()=>{
  const fixture=setup({missingMask:true});
  assert.equal(await fixture.onImageEditSubmit('image',{prompt:'edit',maskSrc:'missing'}),false);
  assert.equal(fixture.queued,undefined);
  assert.equal(fixture.submitted,undefined);
  assert.equal(fixture.record.generation,'original');
});

test('automated composer dispatch does not capture a ticket',()=>{
  const fixture=setup();
  assert.ok(source.includes('(0,E.cI)(w6,()=>w4())'));
  fixture.w4();
  assert.equal(fixture.reads,0);
});

test('dispatch under a different account discards the old ticket',async()=>{
  const fixture=setup();
  await fixture.onImageEditSubmit('image',{prompt:'edit'});
  fixture.changeAccount();
  await fixture.accept({status:'sent'});
  assert.equal(fixture.record.generation,'original');
});

test('a receipt already dispatched under the original account still clears its mark',async()=>{
  const fixture=setup();
  await fixture.onImageEditSubmit('image',{prompt:'edit'});
  const sent=attachContext({},fixture.submitted,fixture.scope,{chatGptAuthenticatedAccountId$:'account'});
  fixture.changeAccount();
  await fixture.runtime.accepted(sent,{status:'sent'},fixture.identity);
  assert.equal(fixture.record,null);
});
