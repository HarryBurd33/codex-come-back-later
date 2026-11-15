"""Generate ignored test fixtures from your pinned local app. Never uploads app code."""
import argparse
import json
from pathlib import Path
import subprocess

from asar_read import Asar
import build_marker as build
import recovery as r


def generate(app):
    build.source(app)
    destination = r.ROOT/'build/test-fixtures'
    r.require(not destination.exists(),'Test fixtures already exist; preserve or remove this generated directory explicitly')
    fixture = r.read_json(r.ROOT/'compatibility/test-modules-27194.json')
    archive = Asar(app/r.ARCHIVE);sources = {}
    for item in fixture['modules'].values():
        filename = item['file']
        r.require('/' not in filename and filename.endswith('.js'),'Unexpected fixture source path')
        if filename not in sources:sources[filename] = archive.read('/webview/assets/async/'+filename).decode()
        r.require(r.digest(sources[filename].encode()) == item['sha256'],'Fixture source hash differs')
    exporter = '''
import {readFileSync} from 'node:fs';
const {fixture,sources}=JSON.parse(readFileSync(0,'utf8'));
const tables={};
for (const [name,source] of Object.entries(sources)) {
  if(!/^(?:\\/\\*! LICENSE:[^\\n]*\\n)?export const __rspack_esm_ids=/.test(source))throw Error('Unrecognized source table');
  const table=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  if(Object.keys(table).sort().join(',')!=='__rspack_esm_ids,__webpack_modules__')throw Error('Unexpected exports');
  tables[name]=table.__webpack_modules__;
}
for(const [id,item] of Object.entries(fixture.modules)) {
  const source=tables[item.file][id]?.toString();
  if(!source)throw Error('Missing factory '+id);
  item.source=source;
}
process.stdout.write(JSON.stringify(fixture));
'''
    result = subprocess.run(['node','--input-type=module','-e',exporter],
                            input=json.dumps({'fixture':fixture,'sources':sources}),text=True,capture_output=True,
                            check=True,timeout=60)
    # This config is never launched; overlay generation only needs its JSON prefix.
    replacements = build.overlay(app,{'purpose':'offline-fixture-only'})
    destination.mkdir(parents=True,mode=0o700)
    r.write_json(destination/'modules.json',json.loads(result.stdout))
    targets = build.pins()['targets']
    r.write_json(destination/'scan.json',{'found':targets})
    records = []
    for target in targets:
        name = target['path'];path = destination/'overlay'/name
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(replacements[name])
        records.append({'path':name,'before_sha256':target['sha256'],'after_sha256':r.digest(replacements[name])})
    r.write_json(destination/'overlay-manifest.json',{'files':records})
    return {'generated':str(destination),'modules':len(fixture['modules']),'uploaded':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(generate(args.app),indent=2))
