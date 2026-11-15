import test from 'node:test';
import assert from 'node:assert/strict';
import {createRuntime} from '../src/runtime.mjs';
import {transition} from '../src/state.mjs';

const identity={accountId:'review-account',hostId:'local',threadId:'A'};

test('a marking created while the initial capture is pending survives that submission',async()=>{
  let current={generation:'before-click'},release;
  let opened=false;
  const ready=new Promise(resolve=>{release=resolve;});
  const store={
    read:async()=>{await ready;return current;},
    snapshot:()=>opened ? Promise.resolve(current) : null,
    change:async(_,command)=>{current=transition(current,command);}
  };
  const runtime=createRuntime({store,randomUUID:()=> 'unused'});
  const pending=runtime.capture(runtime.human({}),identity);
  // A second window finishes marking while this connection is still opening.
  current={generation:'marked-after-click'};
  opened=true;
  release();
  const context=runtime.attach({},await pending);
  await runtime.accepted(context,{status:'sent'},identity);
  assert.deepEqual(current,{generation:'marked-after-click'});
});

test('re-entering capture with an existing human ticket never adopts a newer marking',async()=>{
  let current={generation:'original'};
  const store={read:async()=>current,snapshot:()=>Promise.resolve(current),change:async(_,command)=>{current=transition(current,command);}};
  const runtime=createRuntime({store,randomUUID:()=> 'unused'});
  const origin=runtime.human({});
  const options=await runtime.capture(origin,identity);
  current={generation:'newer'};
  const replayed=await runtime.capture(options,identity);
  await runtime.accepted(runtime.attach({},replayed),{status:'sent'},identity);
  assert.deepEqual(current,{generation:'newer'});
  await runtime.accepted(runtime.attach({},runtime.capture({...origin},identity)),{status:'sent'},identity);
  assert.deepEqual(current,{generation:'newer'});
  await runtime.accepted(runtime.attach({},runtime.capture(runtime.human(options),identity)),{status:'sent'},identity);
  assert.equal(current,null);
});

for (const snapshot of [() => Promise.reject(Error('read failed')), () => {throw Error('closed');}, () => Promise.resolve(null)]) {
  test('a failed or empty snapshot stays negative and allows local queue acknowledgement',async()=>{
    let writes=0;
    const store={snapshot,change:()=>{writes++;}};
    const runtime=createRuntime({store,randomUUID:()=> 'unused'});
    const options=runtime.capture(runtime.human({}),identity);
    const context=runtime.attach({},options);
    await runtime.accepted(context,{status:'sent'},identity);
    assert.equal(runtime.requiresReceipt(context),false);
    store.snapshot=()=>Promise.resolve({generation:'newly-marked'});
    await runtime.accepted(runtime.attach({},runtime.capture(options,identity)),{status:'sent'},identity);
    assert.equal(writes,0);
  });
}
