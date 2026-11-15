import {markerKey, isAccepted} from './state.mjs';
import {BrowserStore} from './browser-store.mjs';

// Symbols never cross the app's JSON RPC boundary or enter stored conversations.
const ticketField = Symbol('come-back-later-human-submission');
const originField = Symbol('come-back-later-explicit-composer-action');

export function createRuntime({store, randomUUID, channel}) {
  const cache = new Map();
  const listeners = new Map();
  const epochs = new Map();
  const submissions = new WeakMap();
  const emit = key => listeners.get(key)?.forEach(fn => fn());
  const bump = key => { const value = (epochs.get(key) ?? 0) + 1; epochs.set(key, value); return value; };
  const refresh = async key => {
    const epoch = bump(key);
    const value = await store.read(key);
    if (epochs.get(key) === epoch) { cache.set(key, value?.generation ?? null); emit(key); }
    return value;
  };
  const change = async (key, command) => {
    // Read back after the committed transaction; never publish an optimistic marker.
    await store.change(key, command);
    await refresh(key);
    channel?.postMessage({key});
  };
  if (channel) channel.onmessage = event => {
    const key = event.data?.key;
    if (typeof key === 'string' && listeners.has(key)) refresh(key).catch(() => {});
  };
  const safeKey = identity => { try { return markerKey(identity); } catch { return null; } };
  const api = {
    isHuman(options) { return options?.[originField] != null; },
    human(options) {
      const fresh = {...options, [originField]: {}};
      delete fresh[ticketField];
      return fresh;
    },
    capture(options, identity) {
      const origin = options?.[originField];
      if (!origin || options[ticketField]) return options;
      const existing = submissions.get(origin);
      if (existing) return {...options, [ticketField]: existing};
      const key = safeKey(identity);
      let read = null;
      try { if (key !== null) read = store.snapshot(key); }
      catch { /* A storage failure must not stop a prompt. */ }
      let generation = read == null ? null : undefined;
      const snapshot = Promise.resolve(read).then(
        record => generation = record?.generation ?? null,
        () => generation = null
      );
      const ticket = Object.freeze({key, accountId:identity?.accountId, snapshot, requiresReceipt: () => generation !== null});
      submissions.set(origin, ticket);
      return {...options, [ticketField]: ticket};
    },
    attach(context, options, currentIdentity) {
      const ticket = options?.[ticketField];
      if (ticket == null || (currentIdentity && ticket.accountId !== currentIdentity.accountId)) return context;
      return {...context, [ticketField]: ticket};
    },
    requiresReceipt(context) { return context?.[ticketField]?.requiresReceipt() ?? false; },
    async accepted(context, result, identity) {
      const ticket = context?.[ticketField];
      if (ticket?.key == null || !isAccepted(result)) return;
      let storedIdentity;
      try { storedIdentity = JSON.parse(ticket.key); } catch { return; }
      if (identity.hostId !== storedIdentity[1] || identity.threadId !== storedIdentity[2]) return;
      const generation = await ticket.snapshot;
      if (generation === null) return;
      try { await change(ticket.key, {type:'accepted', generation, result}); }
      catch { /* Retain the marker if persistence fails; never falsely show it cleared. */ }
    },
    wrapMenu(getItems, identity) {
      return async (...args) => {
        const items = await getItems(...args);
        const key = safeKey(identity);
        if (key == null) return items;
        let current;
        try { current = await store.read(key); }
        catch { return items; } // Marker storage must not disable the native menu.
        return [...items, {
          id: 'come-back-later',
          message: {id: current ? 'local.comeBackLater.remove' : 'local.comeBackLater.mark',
            defaultMessage: current ? 'Remove Come back later' : 'Come back later',
            description: 'Toggle the persistent reminder for this chat'},
          onSelect: () => change(key, current ? {type:'unmark'} : {type:'mark',generation:randomUUID()})
        }];
      };
    },
    useRow(React, identity, props) {
      const key = safeKey(identity);
      const subscribe = React.useCallback(callback => {
        if (key == null) return () => {};
        let set = listeners.get(key);
        if (!set) listeners.set(key, set = new Set());
        set.add(callback);
        return () => { set.delete(callback); if (!set.size) listeners.delete(key); };
      }, [key]);
      const snapshot = React.useCallback(() => key == null ? null : cache.get(key) ?? null, [key]);
      const generation = React.useSyncExternalStore(subscribe, snapshot, snapshot);
      React.useEffect(() => { if (key != null) refresh(key).catch(() => {}); }, [key]);
      return React.useMemo(() => {
        if (!generation) return props;
        const marker = React.createElement('span', {
          title: 'Come back later', role:'img', 'aria-label':'Come back later',
          className:'come-back-later-marker',
          style:{display:'inline-flex',flexShrink:0,width:12,height:14,marginInlineEnd:4,color:'light-dark(#956000, #ffc247)'}
        }, React.createElement('svg', {width:12,height:14,viewBox:'0 0 12 14','aria-hidden':true},
          React.createElement('path', {d:'M2 1.5h8v11L6 10l-4 2.5z',fill:'currentColor'})));
        return {...props,titlePrefix:React.createElement(React.Fragment,null,marker,props.titlePrefix)};
      }, [props,generation]);
    }
  };
  return api;
}

if (typeof window !== 'undefined') {
  let indexedDB, channel;
  try { indexedDB = window.indexedDB; } catch { /* Storage access denied. */ }
  const store = new BrowserStore(indexedDB);
  await store.ready.catch(() => {});
  try { channel = new BroadcastChannel('codex-come-back-later-v1'); }
  catch { /* Cross-window refresh is optional. */ }
  globalThis.__codexComeBackLater = createRuntime({store,
    randomUUID: () => crypto.randomUUID(),
    channel});
}
