import test from 'node:test';
import assert from 'node:assert/strict';
import {nativeRequire} from './build27194-path-fixture.mjs';
import {createRuntime} from '../src/runtime.mjs';
import {transition} from '../src/state.mjs';

const identity = {accountId:'fixture-account',hostId:'manager',threadId:'A'};
const require = nativeRequire();
const clone = require('ZEOU');
const omit = require('zMIV');

for (const reMark of [false, true]) {
  test('build27194 packaged clone and omit preserve ticket snapshot; re-mark='+reMark, async () => {
    let record={generation:'original'}, resolve;
    const pending=new Promise(done=>{resolve=done;});
    const runtime=createRuntime({store:{snapshot:()=>pending,read:async()=>record,
      change:async(_,command)=>{record=transition(record,command);}},randomUUID:()=> 'unused'});
    const context=runtime.attach({prompt:'fixture',openingPromptForHistory:'omitted',executorSkillPick:{}},
      runtime.capture(runtime.human({}), identity));
    const cloned=clone({context:omit(context,'openingPromptForHistory','executorSkillPick')}).context;
    assert.equal(cloned.openingPromptForHistory,undefined);
    assert.equal(cloned.prompt,'fixture');
    assert.equal(Object.getOwnPropertySymbols(cloned).length,1);
    assert.equal(runtime.requiresReceipt(cloned),true);
    const field=Object.getOwnPropertySymbols(context)[0];
    assert.equal(cloned[field].snapshot,context[field].snapshot,'native clone retains the Promise');
    assert.equal(cloned[field].requiresReceipt,context[field].requiresReceipt,'closure preserved');
    assert.equal(JSON.stringify(cloned),'{"prompt":"fixture"}');
    if(reMark)record={generation:'new'};
    resolve({generation:'original'});
    await runtime.accepted(cloned,{status:'queued',serverAccepted:true},identity);
    assert.equal(record?.generation??null,reMark?'new':null);
  });
}

for (const change of ['none','account','user','upload-failure']) {
  test('build27194 packaged attachment queue retains captured ticket; change='+change,async()=>{
    let account='fixture-account',user='user',record={generation:'original'},replayed;
    const runtime=createRuntime({store:{snapshot:()=>Promise.resolve(record),read:async()=>record,
      change:async(_,command)=>{record=transition(record,command);}},randomUUID:()=> 'unused'});
    const options=runtime.capture(runtime.human({firstTurnImageAttachmentIds:['image','mask']}),identity);
    await Promise.resolve();
    const timers=[];
    const queue=nativeRequire({zTeN:{vP:(_,value)=>({value})},SPnB:{chatGptAuthenticatedAccountId$:'account',o8:'user'},
      Sd8U:{PR:{}}},['uIyc','dWrR'],{setTimeout:(callback,ms)=>{assert.equal(ms,0);timers.push(callback);}})('uIyc');
    const values=new Map();
    const scope={node:{},get:key=>key==='account'?account:key==='user'?user:values.get(key)??key.value,
      set:(key,value)=>values.set(key,typeof value==='function'?value(values.get(key)??key.value):value)};
    const pending=queue.Mz(scope,{id:'mask-upload'});
    const retire=queue.U_(scope,value=>{replayed=value;});
    assert.equal(queue.lR(scope,options,true),true);
    record={generation:'new'};
    if(change==='account')account='different-account';
    if(change==='user')user='different-user';
    if(change==='upload-failure')pending.fail(Error('fixture upload failed'));else pending.succeed();
    for(const run of timers)run();
    if(change!=='none')assert.equal(replayed,undefined,'native queue rejects stale or failed upload');
    else {
      assert.equal(replayed,options,'native queue retains the original object including symbols');
      await runtime.accepted(runtime.attach({},replayed),{status:'sent'},identity);
    }
    assert.equal(record.generation,'new');
    retire();
  });
}
