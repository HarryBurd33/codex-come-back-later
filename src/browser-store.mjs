import {transition} from './state.mjs';

/** IndexedDB serializes competing read/write transactions across app windows. */
export class BrowserStore {
  #db = null;
  constructor(indexedDB, name = 'codex-come-back-later-v1') {
    this.ready = new Promise((resolve, reject) => {
      const request = indexedDB.open(name, 1);
      let failed = false;
      const fail = error => {
        failed = true;
        clearTimeout(timeout);
        reject(error);
      };
      const timeout = setTimeout(() => fail(new Error('Marker storage open timed out')), 2000);
      request.onupgradeneeded = () => {
        if (failed) request.transaction.abort();
        else request.result.createObjectStore('markers');
      };
      request.onsuccess = () => {
        clearTimeout(timeout);
        const db = request.result;
        if (failed) { db.close(); return; }
        this.#db = db;
        db.onversionchange = () => this.#close(db);
        db.onclose = () => { if (this.#db === db) this.#db = null; };
        resolve(db);
      };
      request.onerror = () => fail(request.error);
      request.onblocked = () => fail(new Error('Marker storage is busy'));
    });
  }
  #read(db, key) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction('markers', 'readonly');
      const request = tx.objectStore('markers').get(key);
      tx.oncomplete = () => resolve(request.result ?? null);
      tx.onabort = () => reject(tx.error ?? request.error);
    });
  }
  // Create the transaction in the caller's stack; never wait for an unopened connection.
  snapshot(key) { return this.#db === null ? null : this.#read(this.#db, key); }
  async read(key) { return this.#read(await this.ready, key); }
  async change(key, command) {
    const db = await this.ready;
    return new Promise((resolve, reject) => {
      const tx = db.transaction('markers', 'readwrite', {durability: 'strict'});
      const store = tx.objectStore('markers');
      const read = store.get(key);
      let next;
      read.onsuccess = () => {
        try {
          next = transition(read.result ?? null, command);
          if (next == null) store.delete(key);
          else store.put(next, key);
        } catch (error) { reject(error); tx.abort(); }
      };
      tx.oncomplete = () => resolve(next);
      tx.onabort = () => reject(tx.error ?? read.error ?? new Error('Marker write failed'));
    });
  }
  #close(db) {
    if (this.#db === db) this.#db = null;
    db.close();
  }
  async close() { this.#close(await this.ready); }
}
