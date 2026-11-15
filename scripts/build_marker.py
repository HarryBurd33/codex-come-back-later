"""Pinned source-only builder. Never launches an app or reads chat/profile contents."""
import copy
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess

from asar_read import Asar
import recovery as r
import stage_archive as a
import native_signing as signing
import native_asar_integrity as integrity
import macho_signature_payload as macho

WORK = r.ROOT/'build/candidates'
ENTRY = '.vite/build/early-bootstrap.js'
LAUNCHER = 'Contents/MacOS/MarkerLauncher'
DISPLAY = 'Codex Marker'
DEFAULT_ID = 'local.codexmarker.app'
COMPATIBILITY = r.ROOT/'compatibility/build-27194.json'


def paths(label):
    directory = r.canonical(WORK/r.name(label))
    return directory,directory/(DISPLAY+'.app')


def pins():
    return r.read_json(COMPATIBILITY)


def source(app):
    r.canonical(app)
    expected = pins()
    info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
    r.require([info.get(k) for k in ('CFBundleIdentifier','CFBundleShortVersionString','CFBundleVersion')] ==
              [expected[k] for k in ('bundle_id','version','build')],'Unsupported original app version')
    r.require(r.file_digest(app/'Contents/Info.plist') == expected['plist_sha256'] and
              r.file_digest(app/r.ARCHIVE) == expected['archive_sha256'],'Original package bytes differ')
    archive = Asar(app/r.ARCHIVE)
    r.require(r.digest(archive.header_bytes) == expected['header_sha256'],'Original ASAR header differs')
    requirement = 'identifier "com.openai.codex" and anchor apple generic and certificate leaf[subject.OU] = "2DC432GLL2"'
    signing.run('/usr/bin/codesign','--verify','--deep','--strict','-R='+requirement,str(app))
    signing.run('/usr/sbin/spctl','--assess','--type','execute',str(app))
    return info


def configuration(app, home, identifier):
    r.require(re.fullmatch(r'[a-z][a-z0-9]*(?:\.[a-z0-9-]+){2,}',identifier) and
              not identifier.startswith('com.openai.'),'Use a separate local bundle identifier')
    home = r.canonical(home)
    r.require(home.is_dir() and home.stat().st_uid == os.getuid(),'Chat home must be an existing user-owned directory')
    root = r.canonical(Path.home()/'Library/Application Support'/identifier)
    result = {'purpose':'come-back-later-existing-chat-install','displayName':DISPLAY,'root':str(root),
              'paths':{k:str(root/k) for k in ('appData','userData','sessionData','logs','crashDumps')},
              'sharedCodexHome':str(home),'originalInfo':str(app/'Contents/Info.plist'),
              'originalBuild':pins()['build'],'originalVersion':pins()['version']}
    if root.exists():
        r.require(root.is_dir() and root.stat().st_uid == os.getuid() and root.stat().st_mode & 0o077 == 0,
                  'Existing private state is unsafe')
        receipt = r.canonical(root/'isolation.json')
        r.require(receipt.is_file() and receipt.read_bytes() == config_bytes(result),
                  'Existing private state belongs to another configuration; preserve it')
    return result


def config_bytes(config):
    return json.dumps(config,separators=(',',':')).encode()


def bootstrap(config):
    template = (r.ROOT/'signing/development-bootstrap.cjs').read_text()
    r.require(template.count('__MARKER_DEV_CONFIG_JSON__') == 1,'Bootstrap template changed')
    return template.replace('__MARKER_DEV_CONFIG_JSON__',config_bytes(config).decode()).encode()


def compile_launcher(config, output, generated_source, *, test=False):
    template = (r.ROOT/'signing/marker-launcher.m').read_text()
    r.require(template.count('__MARKER_CONFIG_C_STRING__') == 1,'Launcher template changed')
    generated_source.write_text(template.replace('__MARKER_CONFIG_C_STRING__',json.dumps(config_bytes(config).decode())))
    command = ['/usr/bin/clang','-arch','arm64','-mmacosx-version-min=14.0','-fobjc-arc',
               '-framework','AppKit',str(generated_source),'-o',str(output)]
    if test:command.insert(1,'-DMARKER_LAUNCHER_TEST=1')
    signing.run(*command)


def overlay(app, config):
    expected = pins();archive = Asar(app/r.ARCHIVE)
    index = archive.read('/webview/index.html');app_entry = expected['app_entry']
    r.require(r.digest(index) == expected['index_sha256'] and
              r.digest(archive.read('/'+app_entry)) == expected['app_entry_sha256'],'Renderer entry differs')
    modules = sorted(m for target in expected['targets'] for m in target['modules'])
    r.require(modules == ['cojq','oprL']+['seW7']*9,'Incomplete patch targets')
    replacements = {}
    for target in expected['targets']:
        data = archive.read('/'+target['path'])
        r.require(r.digest(data) == target['sha256'],'Source chunk differs: '+target['path'])
        result = subprocess.run(['node',str(r.ROOT/'scripts/patch_chunk.mjs')],
                                input=json.dumps({'source':data.decode(),'modules':target['modules'],'build':'27194'}),
                                capture_output=True,text=True,check=True,timeout=60)
        replacements[target['path']] = json.loads(result.stdout)['source'].encode()
    app_url = '/'+app_entry.removeprefix('webview/')
    anchor = f'<script type="module" src="{app_url}">'.encode()
    r.require(index.count(anchor) == 1,'Unexpected renderer script')
    replacements['webview/index.html'] = index.replace(anchor,b'<script type="module" src="/assets/come-back-later/bootstrap.mjs">')
    replacements['webview/assets/come-back-later/bootstrap.mjs'] = (
        'import "./runtime.mjs";\nawait import('+json.dumps(app_url)+');\n').encode()
    for name in ('state.mjs','browser-store.mjs','runtime.mjs'):
        replacements['webview/assets/come-back-later/'+name] = (r.ROOT/'src'/name).read_bytes()
    package = json.loads(archive.read('/package.json'))
    r.require(package['main'] == ENTRY,'Native entry differs')
    package.update(name='codex-marker-local',productName=DISPLAY)
    replacements['package.json'] = (json.dumps(package,indent=2)+'\n').encode()
    replacements[ENTRY] = bootstrap(config)+b'\n'+archive.read('/'+ENTRY)
    return replacements


def verify_archive(original, output, replacements):
    _,before,dirs,_,_,_ = a.archive_index(original)
    _,after,after_dirs,base,_,dense = a.archive_index(output)
    added_dirs = {str(p) for name in replacements for p in Path(name).parents}-{'.'}
    r.require(dense and after.keys() == before.keys()|replacements.keys() and
              after_dirs == dirs|added_dirs,'Archive layout changed unexpectedly')
    with output.open('rb') as stream:
        seen = {}
        for key,node in after.items():
            prior = before.get(key,{})
            metadata = lambda value:{k:v for k,v in value.items() if k not in {'offset','size','integrity'}}
            r.require(metadata(node) == metadata(prior),'Archive node attributes changed')
            if node.get('unpacked'):
                r.require(node == prior,'Unpacked node changed');continue
            extent = (int(node['offset']),node['size'])
            if extent not in seen:
                stream.seek(base+extent[0]);seen[extent] = a.measure(stream,extent[1])
            expected = r.digest(replacements[key]) if key in replacements else prior['integrity']['hash']
            r.require(seen[extent] == node['integrity'] and node['integrity']['hash'] == expected,
                      'Archive readback differs: '+key)


def prepare(label, app, home, identifier=DEFAULT_ID):
    directory,bundle = paths(label)
    r.require(not directory.exists(),'Existing build needs reconciliation; never overwrite it')
    original_info = source(app);config = configuration(app,home,identifier)
    replacements = overlay(app,config);entries = r.tree(app)
    plan = signing.plan(app,identifier)
    WORK.mkdir(parents=True,mode=0o700,exist_ok=True);directory.mkdir(mode=0o700)
    record = {'schema':1,'label':label,'status':'prepare-incomplete','bundle':str(bundle),
              'original_app':str(app),'identifier':identifier,'isolation':config,
              'source_fingerprint':r.fingerprint(entries),'signing_plan':plan}
    r.write_json(directory/'manifest.json',record)
    # Keep a verified complete original before constructing the derivative.
    backup = directory/'original.app';r.copy_bundle(app,backup,entries)
    r.write_json(directory/'original-inventory.json',entries)
    r.copy_bundle(backup,bundle,entries)
    tree,nodes,_,base,_,_ = a.archive_index(backup/r.ARCHIVE)
    output = directory/'app.asar'
    header = a.write_archive(backup/r.ARCHIVE,tree,nodes,base,replacements,output)
    verify_archive(backup/r.ARCHIVE,output,replacements)
    import shutil
    shutil.copyfile(output,bundle/r.ARCHIVE)
    info = copy.deepcopy(original_info)
    info.update(CFBundleIdentifier=identifier,CFBundleName=DISPLAY,CFBundleDisplayName=DISPLAY,
                CFBundleExecutable='MarkerLauncher',CrProductDirName=identifier)
    for key in ('CFBundleURLTypes','CFBundleAlternateNames','CFBundleDocumentTypes',
                'UTExportedTypeDeclarations','UTImportedTypeDeclarations','NSUserActivityTypes'):
        info.pop(key,None)
    info['ElectronAsarIntegrity'][a.INTEGRITY_KEY] = a.integrity_record(header)
    (bundle/'Contents/Info.plist').write_bytes(plistlib.dumps(info,fmt=plistlib.FMT_XML,sort_keys=False))
    framework = next(item for item in plan if item['object'] == signing.FRAMEWORKS[0])
    native = bundle/framework['binary']
    modified,change = integrity.update(native.read_bytes(),original_info['ElectronAsarIntegrity'],info['ElectronAsarIntegrity'])
    native.write_bytes(modified);framework['original_payloads'] = framework['payloads']
    framework['payloads'] = macho.fingerprints(native)
    record['native_integrity_update'] = {'binary':framework['binary'],**change}
    engine = next(item for item in plan if item['object'] == '.');engine['object'] = engine['binary']
    compile_launcher(config,bundle/LAUNCHER,directory/'launcher.m')
    plan.append({'binary':LAUNCHER,'object':'.','identifier':identifier,'entitlements':{},'omitted':{},
                 'payloads':macho.fingerprints(bundle/LAUNCHER)})
    plan.sort(key=lambda v:(-len(Path(v['object']).parts),v['object']=='.',v['object']))
    r.require(len(plan) == 38 and len({v['object'] for v in plan}) == 38,'Unexpected signing closure')
    os.rename(bundle/'Contents/embedded.provisionprofile',directory/'retained-vendor-profile.provisionprofile')
    before = r.tree(bundle)
    expected_paths = entries.keys()-{'Contents/embedded.provisionprofile'}|{LAUNCHER}
    r.require(before.keys() == expected_paths,'Unplanned bundle paths')
    changed = {k for k in before if k not in entries or before[k] != entries[k]}
    r.require(changed == {r.ARCHIVE,'Contents/Info.plist',framework['binary'],LAUNCHER},'Unplanned bundle changes')
    r.write_json(directory/'before-sign.json',before)
    (directory/'entitlements').mkdir(mode=0o700)
    for i,item in enumerate(plan):(directory/'entitlements'/f'{i}.plist').write_bytes(plistlib.dumps(item['entitlements']))
    record.update(status='prepared-not-signed',prepared_fingerprint=r.fingerprint(before),
                  before_sign_sha256=r.file_digest(directory/'before-sign.json'),
                  archive_sha256=r.file_digest(bundle/r.ARCHIVE),archive_header_sha256=header,
                  plist_sha256=r.file_digest(bundle/'Contents/Info.plist'),
                  replacements={k:r.digest(v) for k,v in replacements.items()})
    r.write_json(directory/'manifest.json',record)
    return {'status':record['status'],'bundle':str(bundle),'original_backup':str(backup),'launched':False,'installed':False}


def sign(label, identity):
    directory,bundle = paths(label);record = r.read_json(directory/'manifest.json')
    r.require(record['status'] == 'prepared-not-signed' and
              r.fingerprint(r.tree(bundle)) == record['prepared_fingerprint'],'Build changed or signing outcome uncertain')
    r.require(re.fullmatch('[A-Fa-f0-9]{40}',identity) and
              identity.upper() in {v['fingerprint'] for v in signing.identities()},'Eligible Apple-issued identity unavailable')
    record.update(status='signing-incomplete',identity=identity.upper());r.write_json(directory/'manifest.json',record)
    for i,item in enumerate(record['signing_plan']):
        entitlement = directory/'entitlements'/f'{i}.plist'
        r.require(plistlib.loads(entitlement.read_bytes()) == item['entitlements'],'Entitlements changed')
        signing.run('/usr/bin/codesign','--force','--sign',identity,'--options','runtime','--timestamp=none',
                    '--identifier',item['identifier'],'--entitlements',str(entitlement),str(bundle/item['object']))
    _,record['team'],_ = signing.details(bundle)
    record['bundle_fingerprint'] = signing.validate_signed_contents(directory,bundle,record)
    record['status'] = 'signed-verified'
    result = subprocess.run(['/usr/sbin/spctl','--assess','--type','execute','--verbose=2',str(bundle)],
                            capture_output=True,text=True,timeout=60)
    record['gatekeeper'] = {'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    r.write_json(directory/'manifest.json',record)
    return {'status':'signed-verified','bundle':str(bundle),'fingerprint':record['bundle_fingerprint'],
            'gatekeeper':record['gatekeeper'],'native_launch':'human-test-required','installed':False}
