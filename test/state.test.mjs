import test from 'node:test';
import assert from 'node:assert/strict';
import {markerKey, transition} from '../src/state.mjs';
import {createRuntime} from '../src/runtime.mjs';

const A={accountId:'account-1',hostId:'host-1',threadId:'chat-A'};
const B={...A,threadId:'chat-B'};
class Store {
  records = new Map();
  async read(key) { return this.records.get(key) ?? null; }
  snapshot(key) { return this.read(key); }
  async change(key, command) {
    const next=transition(this.records.get(key)??null,command);
    if(next==null)this.records.delete(key);else this.records.set(key,next);
  }
}
function setup() {
  const store=new Store();let count=0;
  const runtime=createRuntime({store,randomUUID:()=>`generation-${++count}`});
  const mark=async identity => {
    const menu=await runtime.wrapMenu(()=>[],identity)();
    await menu[0].onSelect();
  };
  const begin=async (identity=A,human=true)=>runtime.attach({},await runtime.capture(human?runtime.human({}):{},identity));
  return {store,runtime,mark,begin,read:identity=>store.read(markerKey(identity))};
}

test('opening, reading, renaming, moving, drafts and assistant activity preserve a marking',()=>{
  const marked=transition(null,{type:'mark',generation:'g1'});
  for(const type of ['open','reopen','select','read','switch-away','rename','move','draft','assistant','tool','automated']) {
    assert.deepEqual(transition(marked,{type}),marked,type);
  }
});
test('stable identity isolates account, host and chat without title or project',()=>{
  const keys=[A,B,{...A,hostId:'host-2'},{...A,accountId:'account-2'}].map(markerKey);
  assert.equal(new Set(keys).size,4);
  assert.equal(markerKey({...A,title:'renamed',project:'moved'}),markerKey(A));
  assert.throws(()=>markerKey({...A,accountId:null}));
});
for(const result of [{status:'sent'},{status:'queued',serverAccepted:true}]) {
  test(`confirmed ${result.status} clears only the exact marked chat`,async()=>{
    const x=setup();await x.mark(A);await x.mark(B);
    const context=await x.begin();await x.runtime.accepted(context,result,A);
    assert.equal(await x.read(A),null);assert.ok(await x.read(B));
  });
}
for(const result of [null,{status:'failed'},{status:'rejected'},{status:'outcome-unknown'},
  {status:'queued'},{status:'queued',serverAccepted:false},{status:'queued',serverAccepted:'true'},
  {requestDispatched:true},{status:'completed'}]) {
  test(`nonacceptance ${JSON.stringify(result)} retains marker`,async()=>{
    const x=setup();await x.mark(A);const context=await x.begin();
    await x.runtime.accepted(context,result,A);assert.ok(await x.read(A));
  });
}
test('automated continuation cannot acquire a human submission ticket',async()=>{
  const x=setup();await x.mark(A);const context=await x.begin(A,false);
  assert.equal(x.runtime.requiresReceipt(context),false);
  await x.runtime.accepted(context,{status:'sent'},A);assert.ok(await x.read(A));
});
test('replayed accepted event and delayed event cannot clear a new marking',async()=>{
  const x=setup();await x.mark(A);const context=await x.begin();
  await x.mark(A);await x.mark(A);const newer=await x.read(A);
  await x.runtime.accepted(context,{status:'sent'},A);assert.deepEqual(await x.read(A),newer);
  const fresh=await x.begin();await x.runtime.accepted(fresh,{status:'sent'},A);
  await x.mark(A);const newest=await x.read(A);
  await x.runtime.accepted(fresh,{status:'sent'},A);assert.deepEqual(await x.read(A),newest);
});
test('a prompt begun while unmarked cannot clear a later mark',async()=>{
  const x=setup();const context=await x.begin();await x.mark(A);
  await x.runtime.accepted(context,{status:'sent'},A);assert.ok(await x.read(A));
});
test('mismatched host or chat receipts never clear',async()=>{
  const x=setup();await x.mark(A);const context=await x.begin();
  await x.runtime.accepted(context,{status:'sent'},B);
  await x.runtime.accepted(context,{status:'sent'},{...A,hostId:'other'});
  assert.ok(await x.read(A));
});
test('native menu preserves existing entries and exposes manual removal',async()=>{
  const x=setup();const unread={id:'mark-unread',onSelect(){throw Error('Unread action should not run');}};
  let menu=await x.runtime.wrapMenu(()=>[unread],A)();
  assert.equal(menu[0],unread);assert.equal(menu[1].message.defaultMessage,'Come back later');
  await menu[1].onSelect();menu=await x.runtime.wrapMenu(()=>[unread],A)();
  assert.equal(menu[1].message.defaultMessage,'Remove Come back later');
  await menu[1].onSelect();assert.equal(await x.read(A),null);
});
test('restart recreates runtime while preserving minimal stored metadata',async()=>{
  const x=setup();await x.mark(A);
  const next=createRuntime({store:x.store,randomUUID:()=> 'next'});
  const menu=await next.wrapMenu(()=>[],A)();
  assert.equal(menu[0].message.defaultMessage,'Remove Come back later');
  assert.deepEqual(Object.keys(await x.read(A)),['generation']);
});
test('private ticket is omitted by JSON transport and preserves prompt content',async()=>{
  const x=setup();await x.mark(A);
  const options=await x.runtime.capture(x.runtime.human({}),A);
  const context=x.runtime.attach({prompt:'test prompt',unread:true},options);
  assert.equal(x.runtime.requiresReceipt(context),true);
  assert.equal(JSON.stringify(context),'{"prompt":"test prompt","unread":true}');
  assert.equal(JSON.stringify(await x.read(A)).includes('prompt'),false);
});
test('failed persistence retains the marker and does not reject prompt acceptance',async()=>{
  const x=setup();await x.mark(A);const context=await x.begin();
  x.store.change=async()=>{throw Error('disk unavailable');};
  await x.runtime.accepted(context,{status:'sent'},A);assert.ok(await x.read(A));
});
test('unavailable marker storage leaves existing context-menu actions usable',async()=>{
  const x=setup();let invoked=false;
  const original=[{id:'mark-unread',onSelect(){invoked=true;}}];
  x.store.read=async()=>{throw Error('storage unavailable');};
  const menu=await x.runtime.wrapMenu(()=>original,A)();
  assert.equal(menu,original);
  menu[0].onSelect();assert.equal(invoked,true);
});
