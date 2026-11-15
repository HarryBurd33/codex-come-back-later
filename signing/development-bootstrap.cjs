// Development-copy isolation, evaluated before the unchanged native application entry.
(() => {
  const markerConfig = __MARKER_DEV_CONFIG_JSON__;
  const fs = require('node:fs');
  const path = require('node:path');
  const { app } = require('electron');
  if (app.isReady()) throw new Error('Marker development isolation started too late');
  if (app.commandLine.getSwitchValue('user-data-dir') !== markerConfig.paths.userData)
    throw new Error('Open Codex Marker normally to select its private native profile');
  const ownedDirectory = value => {
    const stat = fs.lstatSync(value);
    if (!stat.isDirectory() || stat.isSymbolicLink() || fs.realpathSync(value) !== value ||
        stat.uid !== process.getuid() || (stat.mode & 0o077) !== 0)
      throw new Error('Marker development state directory is unsafe');
  };
  ownedDirectory(markerConfig.root);
  const receipt = path.join(markerConfig.root, 'isolation.json');
  if (fs.lstatSync(receipt).isSymbolicLink() || fs.realpathSync(receipt) !== receipt ||
      fs.readFileSync(receipt, 'utf8') !== JSON.stringify(markerConfig))
    throw new Error('Marker development isolation record changed');
  for (const value of Object.values(markerConfig.paths)) {
    if (path.dirname(value) !== markerConfig.root)
      throw new Error('Marker development path escaped its state directory');
    ownedDirectory(value);
  }
  const codexHome = markerConfig.sharedCodexHome ?? markerConfig.paths.codex;
  if (markerConfig.sharedCodexHome != null) {
    const stat = fs.lstatSync(codexHome);
    if (markerConfig.purpose !== 'come-back-later-existing-chat-install' ||
        !path.isAbsolute(codexHome) || !stat.isDirectory() || stat.isSymbolicLink() ||
        fs.realpathSync(codexHome) !== codexHome || stat.uid !== process.getuid())
      throw new Error('Existing Codex home is not the reviewed user-owned directory');
  }
  app.setName(markerConfig.displayName ?? 'Codex Marker Development');
  for (const [name, value] of Object.entries(markerConfig.paths)) {
    if (name !== 'codex') app.setPath(name, value);
  }
  // This is the application's documented state-directory setting, scoped to this
  // development process and its children. It does not change the user's environment.
  process.env.CODEX_HOME = codexHome;
  process.env.CODEX_ELECTRON_USER_DATA_PATH = markerConfig.paths.userData;
  // Supported packaged-build switch. This fixed-version personal build is updated
  // only after compatibility review; leave the original app's updater unchanged.
  process.env.CODEX_SPARKLE_ENABLED = 'false';
  for (const [name, value] of Object.entries(markerConfig.paths)) {
    if (name !== 'codex' && app.getPath(name) !== value)
      throw new Error('Marker development path override was not accepted');
  }
  // The packaged startup attempts runtime protocol registration too. Refuse that
  // optional registration so this test copy cannot replace the user's URL handlers.
  Object.defineProperty(app, 'setAsDefaultProtocolClient', { value: () => false });
  const report = path.join(markerConfig.root, 'bootstrap-observation.json');
  const descriptor = fs.openSync(report, fs.constants.O_WRONLY | fs.constants.O_CREAT |
    fs.constants.O_TRUNC | fs.constants.O_NOFOLLOW, 0o600);
  try {
    fs.writeFileSync(descriptor, JSON.stringify({ status: 'isolation-configured-before-ready',
      observedAt: new Date().toISOString(), nativeUserData: app.commandLine.getSwitchValue('user-data-dir'),
      codexHome, updaterEnabled: process.env.CODEX_SPARKLE_ENABLED !== 'false', paths: markerConfig.paths }));
  } finally { fs.closeSync(descriptor); }
})();
