// Current build factories, kept distinct from the build 26605 overlay fixtures.
import {readFile} from 'node:fs/promises';
import {nativeRequire as requireFixture} from './native-path-fixture.mjs';

export const fixture = JSON.parse(await readFile(new URL('../build/test-fixtures/modules.json', import.meta.url)));
export const nativeRequire = (overrides={}, allowed=fixture.pure, globals={}) =>
  requireFixture(overrides, allowed, globals, fixture);
