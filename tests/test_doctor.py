#!/usr/bin/env python3
import importlib.util, json, os, subprocess, sys, unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('doctor',ROOT/'scripts/doctor.py')
doctor=importlib.util.module_from_spec(spec);spec.loader.exec_module(doctor)
cap_spec=importlib.util.spec_from_file_location('capabilities',ROOT/'core/qa/capabilities.py')
capabilities=importlib.util.module_from_spec(cap_spec);cap_spec.loader.exec_module(capabilities)

class FakeProbe:
    def __init__(self,commands=None,pillow=('12.1.1',None),specs=None,venv=False,cjk=True,writable=True):
        self.commands={'node':'/usr/bin/node','npm':'/usr/bin/npm','libreoffice':'/usr/bin/libreoffice',
                       'pdftoppm':'/usr/bin/pdftoppm','fc-list':'/usr/bin/fc-list','fc-match':'/usr/bin/fc-match'}
        if commands is not None:self.commands=commands
        self.pillow=pillow;self.specs={'PIL':pillow[1] is None} if specs is None else specs
        self.venv=venv;self.cjk=cjk;self.writable=writable
        self.versions={'ajv':'8.20.0','jszip':'3.10.2','pptxgenjs':'4.0.0','image-size':'2.0.4'}
    def which(self,name):return self.commands.get(name)
    def find_spec(self,name):return object() if self.specs.get(name) else None
    def is_executable(self,path):return bool(path)
    def run(self,args,timeout=8):
        if args[0].endswith('node') and args[-1]=='--version':return SimpleNamespace(returncode=0,stdout='v24.18.0\n',stderr='')
        if args[0].endswith('npm') and args[-1]=='--version':return SimpleNamespace(returncode=0,stdout='11.19.1\n',stderr='')
        if 'fc-match' in args[0]:
            if not self.cjk:return SimpleNamespace(returncode=0,stdout='DejaVu Sans|Book\n',stderr='')
            return SimpleNamespace(returncode=0,stdout=('Noto Sans CJK SC|Bold\n' if ':bold' in args[-1] else 'Noto Sans CJK SC|Regular\n'),stderr='')
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    def python_version(self):return (3,14,4)
    def python_executable(self):return '/usr/bin/python3'
    def package_version(self,name):return self.versions.get(name)
    def pillow_version(self):return self.pillow
    def exists(self,path):return self.venv
    def venv_python(self,venv):return (Path(venv)/'bin/python') if self.venv else None
    def venv_pillow_version(self,venv):return '12.1.1' if self.venv else None
    def can_write(self,path):return (True,None) if self.writable else (False,'denied')
    def platform_info(self):return {'system':'Linux','release':'test','machine':'x86_64','platform':'linux',
                                    'current':'linux','wsl':False,'wsl_distro':None}

class DoctorTests(unittest.TestCase):
    def test_missing_required_is_blocked_and_nonzero(self):
        probe=FakeProbe(commands={'libreoffice':'/usr/bin/libreoffice','pdftoppm':'/usr/bin/pdftoppm'})
        result=doctor.inspect(probe)
        self.assertEqual(result['status'],'BLOCKED')
        node=next(c for c in result['checks'] if c['id']=='node')
        self.assertEqual((node['requirement'],node['status']),('REQUIRED','MISSING'))
        self.assertTrue(result['summary']['blocked'])
        self.assertEqual(result['capabilities']['ladder']['VISUAL_REVIEW']['status'],'REQUIRES_REVIEWER')
        self.assertEqual(result['capabilities']['ladder']['SPEC_ONLY']['status'],'UNAVAILABLE')
        self.assertNotEqual(result['visual_qa'],'PASS')
    def test_missing_optional_explains_impact_and_never_claims_visual_pass(self):
        probe=FakeProbe(commands={'node':'/usr/bin/node','npm':'/usr/bin/npm'},pillow=(None,'Pillow is not installed'),specs={'PIL':False})
        result=doctor.inspect(probe)
        self.assertEqual(result['status'],'READY_WITH_NOTES')
        gaps=[c for c in result['checks'] if c['requirement']=='OPTIONAL' and c['status']!='PRESENT']
        self.assertTrue(gaps)
        for item in gaps:
            self.assertTrue(item['impact'],item['id'])
            self.assertTrue(item['recovery'],item['id'])
        self.assertEqual(result['capabilities']['ladder']['NATIVE_RENDER']['status'],'UNAVAILABLE')
        self.assertEqual(result['capabilities']['ladder']['VISUAL_REVIEW']['status'],'REQUIRES_REVIEWER')
        self.assertIn(result['visual_qa'],{'UNAVAILABLE','NOT_RUN'})
        self.assertFalse(any(c['status']=='PASS' for c in result['checks']))
    def test_present_commands_are_not_execution_pass(self):
        result=doctor.inspect(FakeProbe())
        libreoffice=next(c for c in result['checks'] if c['id']=='libreoffice')
        self.assertEqual(libreoffice['status'],'PRESENT')
        self.assertIn('execution not verified',libreoffice['detail'])
        self.assertEqual(result['capabilities']['ladder']['NATIVE_RENDER']['status'],'AVAILABLE')
        self.assertIn('not proven',result['capabilities']['ladder']['NATIVE_RENDER']['note'])
        self.assertEqual(result['visual_qa'],'NOT_RUN')
        self.assertEqual(result['status'],'READY_WITH_NOTES')
        self.assertEqual(result['capabilities']['ladder']['SPEC_ONLY']['status'],'AVAILABLE')
        font=next(c for c in result['checks'] if c['id']=='fonts')
        self.assertIn('heuristic',font['detail'])
        self.assertIn('glyph coverage is not verified',font['detail'])
    def test_missing_js_dependencies_disable_spec_capability(self):
        probe=FakeProbe();probe.versions={}
        result=doctor.inspect(probe)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['capabilities']['ladder']['SPEC_ONLY']['status'],'UNAVAILABLE')
        js=next(c for c in result['checks'] if c['id']=='js-dependencies')
        self.assertEqual(js['status'],'MISSING')
    def test_missing_pillow_metadata_is_missing_not_broken(self):
        probe=FakeProbe(pillow=(None,None),specs={'PIL':False})
        result=doctor.inspect(probe)
        pillow=next(c for c in result['checks'] if c['id']=='pillow')
        self.assertEqual(pillow['status'],'MISSING')
    def test_platform_and_wsl_reporting(self):
        probe=FakeProbe();probe.platform_info=lambda:{'system':'Linux','release':'test','machine':'x86_64','platform':'linux',
                                                       'current':'linux','wsl':True,'wsl_distro':'Ubuntu'}
        result=doctor.inspect(probe)
        self.assertTrue(result['platform']['wsl'])
        self.assertEqual(result['platform']['support'],{'linux':'AVAILABLE','darwin':'NOT_RUN','win32':'NOT_RUN'})
        platform_check=next(c for c in result['checks'] if c['id']=='platform')
        self.assertIn('WSL',platform_check['detail'])
    def test_unknown_platform_is_reported_not_mapped_to_linux(self):
        probe=FakeProbe();probe.platform_info=lambda:{'system':'FreeBSD','release':'test','machine':'amd64','platform':'freebsd13',
                                                       'current':'freebsd13','wsl':False,'wsl_distro':None}
        result=doctor.inspect(probe)
        self.assertEqual(result['platform']['support'],{'linux':'NOT_RUN','darwin':'NOT_RUN','win32':'NOT_RUN'})
        platform=next(c for c in result['checks'] if c['id']=='platform')
        self.assertEqual(platform['status'],'UNSUPPORTED')
        self.assertIn('without normalization',platform['detail'])
    def test_standalone_capabilities_require_node(self):
        original=capabilities.shutil.which
        capabilities.shutil.which=lambda name:None if name=='node' else original(name)
        try:self.assertFalse(capabilities.js_ready())
        finally:capabilities.shutil.which=original
    def test_generated_at_is_timezone_aware_seconds_iso(self):
        value=doctor.inspect(FakeProbe())['generated_at']
        self.assertRegex(value,r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$')
        parsed=datetime.fromisoformat(value)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.microsecond,0)
        self.assertEqual(parsed.isoformat(timespec='seconds'),value)
        self.assertLess(abs((datetime.now(timezone.utc)-parsed.astimezone(timezone.utc)).total_seconds()),300)
    def test_cli_missing_required_exits_nonzero(self):
        env={**os.environ,'PATH':''}
        process=subprocess.run([sys.executable,str(ROOT/'scripts/doctor.py'),'--json'],capture_output=True,text=True,env=env)
        self.assertNotEqual(process.returncode,0)
        result=json.loads(process.stdout)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('node',[c['id'] for c in result['checks'] if c['requirement']=='REQUIRED' and c['status']!='PRESENT'])

if __name__=='__main__':unittest.main()
