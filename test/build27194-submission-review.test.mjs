// Review harness: real patched seW7 factory, inert native services. No IPC/app launch.
import test from 'node:test';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRuntime} from '../src/runtime.mjs';
import {transition} from '../src/state.mjs';
import {nativeRequire,fixture} from './build27194-path-fixture.mjs';

const utilities=nativeRequire();
const clone=utilities('ZEOU');
const omit=utilities('zMIV');
const normalize=nativeRequire({kHl2:{k:[{field:'fixtureContext',key:'fixture',kind:'trusted',render:v=>v}]}},
  ['Vrnh','dHwh'])('Vrnh').jA;

const scan=JSON.parse(await readFile(new URL('../build/test-fixtures/scan.json',import.meta.url)));
const targets=scan.found.filter(x=>x.modules.includes('seW7'));
assert.equal(targets.length,9);
const manifest=JSON.parse(await readFile(new URL('../build/test-fixtures/overlay-manifest.json',import.meta.url)));
const identity={accountId:'review',hostId:'manager',threadId:'A'};
const noop=()=>{};

function nativeLocalSubmit(submit, scope) {
  // Execute the actual aVy5 local dispatcher. Unexecuted services are inert;
  // any unexpected callable dependency fails rather than reaching the app.
  const deps=Object.fromEntries([...fixture.modules.aVy5.source.matchAll(/\bn\("([^"]+)"\)/g)]
    .map(([,id])=>[id,{}]));
  const schema={safeParse:()=>({data:undefined}),optional(){return this;}};
  const lifecycle=nativeRequire({ASxG:{object:()=>schema,string:()=>schema,enum:()=>schema}},['CDw0'])('CDw0');
  Object.assign(deps,{seW7:{h:submit},CDw0:lifecycle,HK0a:{jz:noop},
    x0TY:{jl:()=>noop},lbJY:{BK:()=>noop},dW2U:{Y:noop},tl5a:{qX:'host-selector',VT:'turn-count'},
    fj7z:{bz:'memory'},V3rO:{Pt:'pending'}});
  const dispatcher=nativeRequire(deps,['aVy5'])('aVy5').N({
    scope,followUp:{type:'local',localConversationId:'A'},isResponseInProgress:true,
    resolvedHostId:'execution-host',setEffectiveCollaborationMode:noop,
    // Real cloning through both optional hooks before aVy5 dispatches to seW7.
    captureLocalSubmitContext:context=>clone(context),
    prepareLocalSubmit:async context=>clone({...context,additionalContext:{fixture:'prepared'}}),
    localFollowUpPreparation:'before-admission'
  });
  return dispatcher.handleSubmitLocal;
}

for (const target of targets) {
  test('build27194 submission factory: '+target.path,async()=>{
    const source=await readFile(new URL('../build/test-fixtures/overlay/'+target.path,import.meta.url),'utf8');
    const entry=manifest.files.find(entry=>entry.path===target.path);
    assert.equal(entry?.before_sha256,target.sha256);
    assert.equal(createHash('sha256').update(source).digest('hex'),entry.after_sha256);
    const factory=(await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))).__webpack_modules__.seW7;
    for(const receipt of [{status:'sent'}, {status:'queued',serverAccepted:true},
      {status:'queued',serverAccepted:false}, {status:'outcome-unknown'}]) {
      let record={generation:'original'},sendArgs,show;
      const displayed=new Promise(resolve=>{show=resolve;});
      const store={snapshot:()=>Promise.resolve(record),read:async()=>record,
        change:async(_,command)=>{record=transition(record,command);}};
      const runtime=createRuntime({store,randomUUID:()=> 'unused'});
      globalThis.__codexComeBackLater=runtime;
      const context=runtime.attach({prompt:'fixture',userMessageFormat:'text',fixtureContext:'fixture-only'},
        runtime.capture(runtime.human({}),identity));
      const manager={
        getFollowUpContext:async()=>({resumeState:'resumed'}),
        getTurnCoordinator:async()=>({sendMessage:async args=>{sendArgs=args;return receipt;}})
      };
      // Real packaged clone/omit/normalization. Only the normalization registry
      // and native services are controlled; this still does not execute IPC.
      const deps={
        SRbQ:{mS:(_,value)=>value,hk:state=>{if(state.hasError)throw state.error;}},
        ZEOU:clone,
        zMIV:omit,
        gp55:{Q3:noop},Dgwo:{V:()=>manager},syw5:{I:()=>null},
        kpNK:{n:()=>false},Vrnh:{jA:normalize},Yn2j:{V:(_,__,value)=>value},
        r0y7:{tu:async()=>null},Oo9D:{gG:async()=>{}},TYK1:{F:async()=>false},
        JQtI:{N:()=>false},qMca:{D0:'guard'},tl5a:{m8:'roots'},
        Ryoj:{c:()=>({displayed})},Ld2s:{t:(_,value,callback)=>callback(value)}
      };
      const require=id=>deps[id]??{};
      require.n=value=>()=>value;
      require.d=(exports,getters,values={})=>{
        for(const [key,get] of Object.entries(getters))Object.defineProperty(exports,key,{get});
        Object.assign(exports,values);
      };
      const exports={};factory({},exports,require);
      let finished=false;
      const scope={value:{kind:'local',placement:receipt.status==='sent'?'side':'main',conversationId:'A'},
        get:selector=>selector==='host-selector'?'manager':selector==='turn-count'?1:null,
        watch:()=>noop};
      const submit=nativeLocalSubmit(descriptor=>{
        assert.equal(descriptor.managerHostId,'manager');
        assert.equal(descriptor.hostId,'execution-host');
        assert.equal(descriptor.targetConversationId,'A');
        assert.equal(runtime.requiresReceipt(descriptor.context),true);
        return exports.h(descriptor,{acceptLocally:true});
      },scope);
      const result=submit(context,'/fixture',undefined,undefined,undefined,'fixture-id',
        {acceptLocally:true},noop)
        .then(value=>value.messageResult)
        .then(value=>{finished=true;return value;});
      // Waiting one macrotask allows the native factory to reach its displayed gate.
      await new Promise(resolve=>setImmediate(resolve));
      assert.ok(sendArgs,'native factory reached coordinator');
      assert.equal(runtime.requiresReceipt(sendArgs.message.context),true,'ticket survives real helpers');
      assert.equal(sendArgs.message.context.fixtureContext,null,'real normalization branch executed');
      assert.equal(sendArgs.message.context.additionalContext.fixture.value,'fixture-only');
      assert.equal(Object.getOwnPropertySymbols(sendArgs.message.context).length,1);
      assert.equal(Object.getOwnPropertySymbols(JSON.parse(JSON.stringify(sendArgs.message.context))).length,0);
      assert.equal(sendArgs.acceptLocally,false,'marked prompt needs server acknowledgement');
      assert.equal(finished,false,'native display gate still pending');
      assert.equal(record===null,receipt.status==='sent'||receipt.serverAccepted===true,
        'clearing occurs on confirmed acceptance, before display/assistant completion');
      show();assert.equal(await result,receipt);
    }
  });
}
