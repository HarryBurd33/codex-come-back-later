// Execute the real inline config queue with controlled React hooks and no UI/IPC.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {nativeRequire} from './build27194-path-fixture.mjs';
import {createRuntime} from '../src/runtime.mjs';
import {transition} from '../src/state.mjs';
const chunk=await readFile(new URL('../build/test-fixtures/overlay/webview/assets/async/486887.8844429c7e.js',import.meta.url),'utf8');
// This file is an export table; importing it never invokes a packaged factory.
const composer=(await import('data:text/javascript;base64,'+Buffer.from(chunk).toString('base64'))).__webpack_modules__.cojq.toString();
const anchor='let{queueSubmit:I}=function(e){';
assert.equal(composer.split(anchor).length,2);
const start=composer.indexOf(anchor)+anchor.indexOf('function');
const end=composer.indexOf('}(o);return m[14]',start);
assert.ok(end>start);
const source=composer.slice(start,end+1);
const imageSession=nativeRequire({},['dWrR'])('dWrR');

function queueHarness() {
  const memo=Array(32).fill(Symbol.for('react.memo_cache_sentinel')),refs=[],effects=[],cleanups=[];
  let refIndex=0,pending=false,replayed,account='review',user='user';
  const scope={get:key=>key==='account'?account:key==='user'?user:pending,set:(_,value)=>{pending=value;}};
  const hooks={useContext:()=>null,useRef:initial=>refs[refIndex++]??(refs[refIndex-1]={current:initial}),
    useLayoutEffect:fn=>effects.push(()=>{const cleanup=fn();if(cleanup)cleanups.push(cleanup);}),
    useEffect:fn=>effects.push(fn),useEffectEvent:fn=>fn};
  const hook=new Function('a','c','f','tI','hT','ok','nO','hk','P','return ('+source+')')(
    {c:()=>memo},{gh:()=>scope,Ul:()=>pending},hooks,{PR:{}},{$w:{}},{CD:{}},{K:fn=>fn},imageSession,{chatGptAuthenticatedAccountId$:'account',o8:'user'});
  const submitComposer=options=>{replayed=options;};
  return {
    render(configPending=true,target='manager:A'){
      refIndex=0;
      // Layout setup only needs to run on initial mount for stable scope/context.
      let layout=hooks.useLayoutEffect;
      if(refs.length)hooks.useLayoutEffect=()=>{};
      const result=hook({isConfigPending:configPending,configTargetKey:'config',submitTargetKey:target,submitComposer});
      hooks.useLayoutEffect=layout;
      while(effects.length)effects.shift()();
      return result;
    },get replayed(){return replayed;},changeAccount(){account='other';},changeUser(){user='other';},unmount(){for(const cleanup of cleanups)cleanup();}
  };
}
const identity={accountId:'review',hostId:'manager',threadId:'A'};
for(const scenario of ['accepted','remarked','negative-snapshot','target-changed','unmounted','account-changed','user-changed']) {
  test('build27194 config queue ticket: '+scenario,async()=>{
    let record=scenario==='negative-snapshot'?null:{generation:'original'};
    const runtime=createRuntime({store:{snapshot:()=>Promise.resolve(record),read:async()=>record,
      change:async(_,command)=>{record=transition(record,command);}},randomUUID:()=> 'unused'});
    const options=runtime.capture(runtime.human({promptRawOverride:'fixture'}),identity);
    globalThis.__codexComeBackLater=runtime;
    const queue=queueHarness();
    assert.equal(queue.render().queueSubmit({type:'composer',options}),true);
    await Promise.resolve();
    if(scenario==='remarked'||scenario==='negative-snapshot')record={generation:'new'};
    if(scenario==='unmounted')queue.unmount();
    if(scenario==='account-changed')queue.changeAccount();
    if(scenario==='user-changed')queue.changeUser();
    queue.render(false,scenario==='target-changed'?'other:B':'manager:A');
    if(['target-changed','unmounted','account-changed','user-changed'].includes(scenario))assert.equal(queue.replayed,undefined);
    else {
      assert.equal(queue.replayed,options,'options and symbol ticket retained, no reconstruction');
      await runtime.accepted(runtime.attach({},queue.replayed),{status:'sent'},identity);
    }
    assert.equal(record?.generation??null,scenario==='accepted'?null:
      ['remarked','negative-snapshot'].includes(scenario)?'new':'original');
  });
}
