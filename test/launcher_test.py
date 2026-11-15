"""Compile and run only owned launcher/engine fixtures. Never launches Codex or GUI."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_marker as a


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.shared=self.root/'existing-home';self.shared.mkdir();(self.shared/'keep').write_text('unchanged')
        self.state=self.root/'private-state';self.mac=self.root/'Fixture.app/Contents/MacOS';self.mac.mkdir(parents=True)
        self.info=self.root/'OriginalInfo.plist'
        self.info.write_bytes(plistlib.dumps({'CFBundleVersion':'27194','CFBundleShortVersionString':'26.1111.21308'}))
        self.config={'purpose':'come-back-later-existing-chat-install','root':str(self.state),
                     'paths':{k:str(self.state/k) for k in ('appData','userData','sessionData','logs','crashDumps')},
                     'sharedCodexHome':str(self.shared),'originalInfo':str(self.info),
                     'originalBuild':'27194','originalVersion':'26.1111.21308'}
        self.launcher=self.mac/'MarkerLauncher'
        a.compile_launcher(self.config,self.launcher,self.root/'launcher.m',test=True)
        engine=self.root/'engine.c'
        engine.write_text('#include <stdio.h>\n#include <stdlib.h>\nint main(int n,char**v){puts(getenv("CODEX_HOME"));puts(getenv("CODEX_ELECTRON_USER_DATA_PATH"));puts(getenv("CODEX_SPARKLE_ENABLED"));for(int i=1;i<n;i++)puts(v[i]);return 0;}\n')
        subprocess.run(['/usr/bin/clang','-arch','arm64',str(engine),'-o',str(self.mac/'ChatGPT')],check=True,capture_output=True)

    def run_launcher(self,*args):
        return subprocess.run([str(self.launcher),*args],capture_output=True,text=True,timeout=10)

    def test_normal_launch_preserves_engine_args_and_shared_state(self):
        result=self.run_launcher('preserved-argument');self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.splitlines(),[str(self.shared),str(self.state/'userData'),'false',
                          'preserved-argument','--user-data-dir='+str(self.state/'userData')])
        self.assertEqual((self.state/'isolation.json').read_bytes(),a.config_bytes(self.config))
        self.assertEqual(self.state.stat().st_mode&0o777,0o700)
        self.assertEqual((self.shared/'keep').read_text(),'unchanged')
        self.assertEqual(self.run_launcher().returncode,0)

    def test_changed_original_build_stops_before_creating_private_state(self):
        self.info.write_bytes(plistlib.dumps({'CFBundleVersion':'updated','CFBundleShortVersionString':'26.1111.21308'}))
        result=self.run_launcher();self.assertNotEqual(result.returncode,0)
        self.assertIn('compatibility review',result.stderr);self.assertFalse(self.state.exists())

    def test_changed_or_symlinked_receipt_is_not_overwritten(self):
        self.assertEqual(self.run_launcher().returncode,0)
        receipt=self.state/'isolation.json';receipt.write_bytes(b'changed')
        self.assertNotEqual(self.run_launcher().returncode,0);self.assertEqual(receipt.read_bytes(),b'changed')
        receipt.unlink();receipt.symlink_to(self.shared/'keep')
        self.assertNotEqual(self.run_launcher().returncode,0);self.assertEqual((self.shared/'keep').read_text(),'unchanged')

    def test_unknown_existing_state_and_symlinked_shared_home_are_preserved(self):
        self.state.mkdir(mode=0o700)
        self.assertNotEqual(self.run_launcher().returncode,0);self.assertEqual(list(self.state.iterdir()),[])
        self.state.rmdir();moved=self.root/'moved-home';self.shared.rename(moved);self.shared.symlink_to(moved)
        self.assertNotEqual(self.run_launcher().returncode,0);self.assertFalse(self.state.exists())

    def test_custom_native_profile_cannot_override_owned_profile(self):
        result=self.run_launcher('--user-data-dir=/unexpected')
        self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,'')
        self.assertIn('normally',result.stderr)


if __name__=='__main__':unittest.main()
