// Packaged factories executed offline. Only explicitly selected pure helpers run.
// Native services, selectors and UI hooks are supplied by each test, never IPC.
import {readFile} from 'node:fs/promises';
import {createContext, runInContext} from 'node:vm';

export const fixture = JSON.parse(await readFile(new URL('../build/test-fixtures/modules.json', import.meta.url)));

export function nativeRequire(overrides = {}, allowed = fixture.pure, globals = {}, sourceFixture = fixture) {
  const permitted = new Set(allowed);
  const cache = new Map();
  // No Node process/require, DOM, network or application service in this realm.
  const realm = createContext(globals);
  const require = id => {
    if (Object.hasOwn(overrides, id)) return overrides[id];
    if (cache.has(id)) return cache.get(id).exports;
    if (!permitted.has(id)) throw Error('Unreviewed dependency '+id);
    const source = sourceFixture.modules[id]?.source;
    if (!source) throw Error('Missing packaged factory '+id);
    const factory = runInContext('Object.values({'+source+'})[0]', realm);
    const module = {exports:{}};
    cache.set(id, module);
    factory(module, module.exports, require);
    return module.exports;
  };
  require.n = value => () => value;
  require.d = (exports, getters, values = {}) => {
    for (const [key, get] of Object.entries(getters)) Object.defineProperty(exports, key, {get});
    Object.assign(exports, values);
  };
  require.nmd = module => {module.paths=[]; module.children=[]; return module;};
  require.g = runInContext('globalThis', realm);
  return require;
}
