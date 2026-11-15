import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const template = fs.readFileSync(fileURLToPath(new URL('../signing/development-bootstrap.cjs', import.meta.url)), 'utf8');
function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'marker-isolation-')));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const config = { purpose: 'come-back-later-isolated-development', root,
    paths: Object.fromEntries(['appData','userData','sessionData','logs','crashDumps','codex'].map(k => [k,path.join(root,k)])) };
  for (const value of Object.values(config.paths)) fs.mkdirSync(value, { mode: 0o700 });
  fs.writeFileSync(path.join(root,'isolation.json'),JSON.stringify(config),{mode:0o600});
  const observed = new Map();
  const app = { isReady:()=>false, commandLine:{getSwitchValue:()=>config.paths.userData}, setName:n=>observed.set('name',n),
    setPath:(k,v)=>observed.set(k,v), getPath:k=>observed.get(k) };
  const process = { getuid:()=>os.userInfo().uid, env:{CODEX_HOME:'/unchanged-outside-process'} };
  const run = () => vm.runInNewContext(template.replace('__MARKER_DEV_CONFIG_JSON__',JSON.stringify(config)), {
    require:name => name==='electron'?{app}:name==='node:fs'?fs:name==='node:path'?path:null, process
  });
  return {root,config,app,process,observed,run};
}
test('development entry isolates Electron paths and child state before app code', t => {
  const f=fixture(t); f.run();
  assert.equal(f.process.env.CODEX_HOME,f.config.paths.codex);
  assert.equal(f.process.env.CODEX_ELECTRON_USER_DATA_PATH,f.config.paths.userData);
  assert.equal(f.process.env.CODEX_SPARKLE_ENABLED,'false');
  assert.equal(f.app.setAsDefaultProtocolClient('codex'),false);
  assert.equal(f.app.setAsDefaultProtocolClient('https'),false);
  for(const [name,value] of Object.entries(f.config.paths)) if(name!=='codex') assert.equal(f.observed.get(name),value);
  const report=JSON.parse(fs.readFileSync(path.join(f.root,'bootstrap-observation.json')));
  assert.equal(report.status,'isolation-configured-before-ready');
  assert.deepEqual(report.paths,f.config.paths);
  assert.equal(report.nativeUserData,f.config.paths.userData);
});
test('alongside mode uses existing chat home without changing its files or permissions', t => {
  const f=fixture(t);
  const shared=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'marker-existing-home-')));
  t.after(()=>fs.rmSync(shared,{recursive:true,force:true}));
  fs.chmodSync(shared,0o755);fs.writeFileSync(path.join(shared,'keep'),'unchanged');
  f.config.purpose='come-back-later-existing-chat-install';f.config.sharedCodexHome=shared;
  delete f.config.paths.codex;
  fs.writeFileSync(path.join(f.root,'isolation.json'),JSON.stringify(f.config));
  f.run();assert.equal(f.process.env.CODEX_HOME,shared);
  assert.equal(f.process.env.CODEX_ELECTRON_USER_DATA_PATH,f.config.paths.userData);
  assert.equal(fs.statSync(shared).mode&0o777,0o755);
  assert.equal(fs.readFileSync(path.join(shared,'keep'),'utf8'),'unchanged');
  f.config.purpose='wrong';fs.writeFileSync(path.join(f.root,'isolation.json'),JSON.stringify(f.config));
  assert.throws(f.run,/reviewed user-owned/);
});
test('native profile must be selected before process startup', t => {
  const f=fixture(t);f.app.commandLine.getSwitchValue=()=>'';
  assert.throws(f.run,/private native profile/);assert.equal(f.observed.size,0);
  assert.equal(fs.existsSync(path.join(f.root,'bootstrap-observation.json')),false);
});
test('late initialization and changed isolation record fail before path changes', t => {
  const f=fixture(t); f.app.isReady=()=>true;
  assert.throws(f.run,/too late/); assert.equal(f.observed.size,0);
  f.app.isReady=()=>false;fs.writeFileSync(path.join(f.root,'isolation.json'),'changed');
  assert.throws(f.run,/record changed/); assert.equal(f.observed.size,0);
});
test('unsafe permissions and symlink substitution cannot reach real profiles', t => {
  const f=fixture(t);fs.chmodSync(f.config.paths.userData,0o755);
  assert.throws(f.run,/unsafe/);assert.equal(f.observed.size,0);
  fs.chmodSync(f.config.paths.userData,0o700);fs.rmdirSync(f.config.paths.userData);
  fs.symlinkSync(f.config.paths.codex,f.config.paths.userData);
  assert.throws(f.run,/unsafe/);assert.equal(f.observed.size,0);
});
test('unaccepted override and symlinked diagnostic output fail closed', t => {
  const f=fixture(t);f.app.getPath=()=>'/unexpected';
  assert.throws(f.run,/not accepted/);
  f.app.getPath=k=>f.observed.get(k);
  const target=path.join(f.root,'keep');fs.writeFileSync(target,'keep');
  fs.symlinkSync(target,path.join(f.root,'bootstrap-observation.json'));
  assert.throws(f.run);assert.equal(fs.readFileSync(target,'utf8'),'keep');
});
