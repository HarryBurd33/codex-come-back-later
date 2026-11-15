// Current packaged row prefix/parent/selectors; no rendering or app services.
// The marker identity is taken from the generated overlay.
import {readFile} from 'node:fs/promises';
import {createRuntime} from '../src/runtime.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {nativeRequire,fixture} from './build27194-path-fixture.mjs';

const generated=await readFile(new URL('../build/test-fixtures/overlay/webview/assets/async/364303.0848d8d911.js',import.meta.url),'utf8');
const row=generated.slice(generated.indexOf('oprL(e,t,n){'));
const menu=row.match(/let nA=\(0,eA.K\)\((.*?)\),nS=/)?.[1];
assert.ok(menu,'generated native menu wrapper');
const start=row.indexOf('function eN(e)'),end=row.indexOf(';tp[27]',start);
assert.ok(start>=0&&end>start);
const prefix=row.slice(start,end)+';return {native:t_,candidate:__cblIdentity.hostId,identity:__cblIdentity,props:e};}';
const defs={i1:(_,fn)=>({fn}),un:(_,fn)=>({fn:(_,ctx)=>fn(ctx)}),
  T1:(_,create)=>({create}),bD:(_,initial)=>({initial})};
function hostState(fallback='local') {
  const known=Symbol(),managers=Symbol(),summary=Symbol(),values=new Map();
  const map=selector=>{if(!values.has(selector))values.set(selector,new Map());return values.get(selector);};
  const scope={get:(selector,arg)=>{
    if(selector==null)return null;
    if(selector===known)return new Set(['local','remote']);
    if(selector===managers)return ['local','remote'];
    if(selector===summary)return null;
    if(selector.fn)return selector.fn(arg,{get:scope.get,scope});
    if(selector.create)return selector.create(arg,{derived:fn=>({fn})});
    if(selector.initial)return map(selector).has(arg)?map(selector).get(arg):selector.initial(arg);
    throw Error('Unexpected selector');
  },set:(selector,id,value)=>map(selector).set(id,value)};
  const deps=Object.fromEntries([...fixture.modules.QGyr.source.matchAll(/\bn\("([^"]+)"\)/g)].map(([,id])=>[id,{}]));
  Object.assign(deps,{zTeN:defs,OWtl:{u:{}},DBCl:{Q2Y:{}},Wbxh:{F6:()=>null},
    SZCv:()=>false,r6TF:{rZ:()=>fallback},CfsC:{D:managers},XQr6:{sZ:known,Hq:summary}});
  const real=nativeRequire(deps,['JBvZ','Bl6U','QGyr']);
  const selector=real('QGyr').yD;
  const affinity=real('JBvZ'),manager=real('Bl6U').qX;
  const hooks={gh:()=>scope,Ul:key=>key==='account'?'fixture-account':null,_U:scope.get};
  const nativeRow=new Function('__cblRequire','r','d','o','V','Z','ei','u','eI','G','return ('+prefix+')')(
    ()=>({chatGptAuthenticatedAccountId$:'account'}),hooks,{useContext:()=>({}),useState:()=>[false,()=>{}],useRef:()=>({})},
    {c:n=>Array(n).fill(Symbol())},{u:{}},{I:{}},{l:{}},{A:()=>({})},{yD:selector},{fI:'local'});
  globalThis.__codexComeBackLater={useRow:(_,identity,props)=>({...props,titlePrefix:identity})};
  return {scope,affinity,manager,hosts:props=>{
    const {native,candidate,identity,props:rendered}=nativeRow(props);
    assert.equal(identity.accountId,'fixture-account');
    assert.equal(identity.threadId,props.conversationId);
    assert.equal(rendered.titlePrefix,identity);
    return {native,candidate};
  }};
}
for(const [name,props,fallback,expected] of [
  ['explicit host wins',{conversationId:'A',hostId:'remote',threadSummary:{hostId:'local'}},'local','remote'],
  ['summary host wins over fallback',{conversationId:'A',threadSummary:{hostId:'remote'}},'local','remote'],
  ['resolver fallback',{conversationId:'A'},'remote','remote'],
  ['native default',{conversationId:'A'},null,'local'],
  ['no conversation',{},'remote','local']
])test('build27194 row identity: '+name,()=>{
  assert.deepEqual(hostState(fallback).hosts(props),{native:expected,candidate:expected});
});

test('build27194 sidebar navigation aligns row host with composer manager selector',()=>{
  const parent=fixture.modules.qK2L.source;
  const expr=parent.match(/d=(i\?\.hostId\?\?tf\?\?_\.fI),/);
  const navigation=parent.match(/onBeforeNavigate:(\(\)=>\{\(0,p\.Nu\).*?\}),navigationState:/);
  assert.ok(expr&&navigation);
  assert.ok(parent.includes('conversationId:a,sidebarThreadKey:o,hostId:d,'));
  const {scope,affinity,manager,hosts}=hostState();
  for(const host of ['remote','local']) {
    affinity.Nu(scope,'A',host==='remote'?'local':'remote');
    const rowHost=new Function('i','tf','_','return '+expr[1])({hostId:host},null,{fI:'local'});
    assert.deepEqual(hosts({conversationId:'A',hostId:rowHost}),{candidate:host,native:host});
    let activated;
    new Function('p','e6','a','d','i','u','ea','e1','eD','return '+navigation[1])(
      affinity,scope,'A',rowHost,{},
      {V:(_,host)=>({activateThreadSummary:async id=>{activated={host,id};}})},
      error=>{throw error;},false,undefined)();
    assert.equal(scope.get(manager,'A'),rowHost);
    assert.deepEqual(activated,{host:rowHost,id:'A'});
  }
});

test('generated sidebar menu toggles only the row account/host/chat',async()=>{
  const rows=new Map();
  globalThis.__codexComeBackLater=createRuntime({store:{
    read:async key=>rows.get(key),
    change:async (key,command)=>command.type==='mark'?rows.set(key,{generation:command.generation}):rows.delete(key)
  },randomUUID:()=> 'generation'});
  const identity={accountId:'fixture-account',hostId:'remote',threadId:'A'};
  const native={id:'existing'};
  const getItems=new Function('tt','__cblIdentity','return '+menu)(()=>[native],identity);
  const [existing,mark]=await getItems('context-menu');
  assert.equal(existing,native);
  assert.equal(mark.message.defaultMessage,'Come back later');
  await mark.onSelect();
  assert.deepEqual([...rows.keys()],[JSON.stringify(['fixture-account','remote','A'])]);
  const [,remove]=await getItems('context-menu');
  assert.equal(remove.message.defaultMessage,'Remove Come back later');
  await remove.onSelect();
  assert.equal(rows.size,0);
});
