#!/usr/bin/env python3
import importlib.util, json, os, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bootstrap',ROOT/'scripts/bootstrap.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)

class Runner:
    def __init__(self):
        self.calls=[]
    def __call__(self,args,cwd=None,env=None,capture_output=False,text=False,**kwargs):
        assert isinstance(args,list)
        assert 'shell' not in kwargs
        self.calls.append({'args':args,'cwd':cwd,'env':env})
        output=''
        if '-c' in args:
            code=args[args.index('-c')+1]
            if 'sys.version_info' in code:output='3.14.4\n'
            elif 'importlib.metadata' in code:output='12.1.1\n'
            elif 'sys.prefix' in code:
                prefix=str(Path(args[0]).resolve().parent.parent)
                output=json.dumps({'prefix':prefix,'base':'/usr'})+'\n'
        return SimpleNamespace(returncode=0,stdout=output,stderr='')
    def pip_calls(self):
        return [call for call in self.calls if len(call['args'])>2 and call['args'][1:3]==['-m','pip']]

def make_root(directory,with_node_modules=True):
    root=Path(directory)
    (root/'package.json').write_text(json.dumps({'name':'fixture','version':'0.0.0','dependencies':{'ajv':'8.20.0','jszip':'3.10.2','pptxgenjs':'4.0.0'},'overrides':{'image-size':'2.0.4'}}),encoding='utf-8')
    (root/'package-lock.json').write_text('{"lockfileVersion":3}\n',encoding='utf-8')
    (root/'requirements-render.txt').write_text('Pillow==12.1.1\n',encoding='utf-8')
    if with_node_modules:
        for name,version in {'ajv':'8.20.0','jszip':'3.10.2','pptxgenjs':'4.0.0','image-size':'2.0.4'}.items():
            package=root/'node_modules'/name/'package.json';package.parent.mkdir(parents=True,exist_ok=True)
            package.write_text(json.dumps({'name':name,'version':version}),encoding='utf-8')
    return root

class BootstrapTests(unittest.TestCase):
    def test_dry_run_creates_nothing_and_handles_unicode_space_paths(self):
        with tempfile.TemporaryDirectory(prefix='构见 Q4 bootstrap ') as directory:
            root=make_root(directory,with_node_modules=False);runner=Runner();lines=[]
            result=bootstrap.bootstrap(root,dry_run=True,runner=runner,emit=lines.append)
            self.assertEqual(result['status'],'DRY_RUN')
            self.assertFalse((root/'.venv').exists())
            self.assertFalse((root/'node_modules').exists())
            steps={action['step']:action['status'] for action in result['actions']}
            self.assertEqual(steps,{'npm-ci':'PLANNED','venv':'PLANNED','pip-install':'PLANNED'})
            npm_action=next(action for action in result['actions'] if action['step']=='npm-ci')
            self.assertEqual(npm_action['command'][1:],['ci','--no-audit','--no-fund'])
            commands=' '.join(' '.join(action.get('command',[])) for action in result['actions'])
            self.assertIn(str(root),commands)
            self.assertIn('current interpreter',result['python_choice'])
            self.assertFalse(any(call['args'][1:3]==['-m','pip'] for call in runner.calls))
            self.assertTrue(any(str(root) in line for line in lines))
    def test_pip_is_venv_only_and_rerun_skips_completed_steps(self):
        with tempfile.TemporaryDirectory(prefix='构见 Q4 bootstrap ') as directory:
            root=make_root(directory);venv_python=root/'.venv/bin/python';venv_python.parent.mkdir(parents=True);venv_python.write_text('')
            runner=Runner();result=bootstrap.bootstrap(root,python=sys.executable,runner=runner,emit=lambda line:None)
            self.assertEqual(result['status'],'READY')
            pip_calls=runner.pip_calls();self.assertEqual(len(pip_calls),1)
            args=pip_calls[0]['args']
            self.assertEqual(args[0],str(venv_python))
            self.assertIn('install',args);self.assertIn('-r',args)
            self.assertEqual(Path(args[0]).resolve().parents[1],(root/'.venv').resolve())
            self.assertNotIn('--user',args);self.assertFalse(any('sudo' in part for part in args))
            self.assertEqual(pip_calls[0]['env']['PYTHONNOUSERSITE'],'1')
            state=json.loads((root/'.venv/.goujian-bootstrap.json').read_text())
            self.assertEqual(state['requirements_sha256'],bootstrap.file_hash(root/'requirements-render.txt'))
            self.assertTrue(state['npm_ready']);self.assertEqual(state['pillow'],'12.1.1')
            second=bootstrap.bootstrap(root,python=sys.executable,runner=runner,emit=lambda line:None)
            self.assertEqual(second['status'],'READY')
            self.assertEqual(len(runner.pip_calls()),1)
            self.assertEqual({a['step']:a['status'] for a in second['actions']}['pip-install'],'SKIPPED')
    def test_interrupted_partial_venv_is_repaired(self):
        with tempfile.TemporaryDirectory(prefix='构见 Q4 bootstrap ') as directory:
            root=make_root(directory);venv=root/'.venv';venv.mkdir()
            class Repairing(Runner):
                def __call__(self,args,cwd=None,env=None,capture_output=False,text=False,**kwargs):
                    result=super().__call__(args,cwd,env,capture_output,text,**kwargs)
                    if len(args)>2 and args[1:3]==['-m','venv']:
                        target=venv/'bin/python';target.parent.mkdir(parents=True,exist_ok=True);target.write_text('')
                    return result
            result=bootstrap.bootstrap(root,python=sys.executable,runner=Repairing(),emit=lambda line:None)
            self.assertEqual(result['status'],'READY')
            self.assertTrue((root/'.venv/bin/python').is_file())
            self.assertEqual({action['step']:action['status'] for action in result['actions']}['venv'],'OK')
            self.assertTrue((root/'.venv/.goujian-bootstrap.json').is_file())
    def test_no_shell_true_and_no_global_install_flags(self):
        source=(ROOT/'scripts/bootstrap.py').read_text(encoding='utf-8')
        self.assertNotIn('shell=True',source)
        self.assertNotIn('--user',source)
        self.assertNotIn("'sudo'",source)
    def test_failed_pip_does_not_write_state(self):
        with tempfile.TemporaryDirectory(prefix='构见 Q4 bootstrap ') as directory:
            root=make_root(directory);venv_python=root/'.venv/bin/python';venv_python.parent.mkdir(parents=True);venv_python.write_text('')
            class Failing(Runner):
                def __call__(self,args,cwd=None,env=None,capture_output=False,text=False,**kwargs):
                    call=super().__call__(args,cwd,env,capture_output,text,**kwargs)
                    if len(args)>2 and args[1:3]==['-m','pip']:call.returncode=1;call.stderr='network down'
                    return call
            with self.assertRaises(bootstrap.BootstrapError):bootstrap.bootstrap(root,python=sys.executable,runner=Failing(),emit=lambda line:None)
            self.assertFalse((root/'.venv/.goujian-bootstrap.json').exists())
    def test_lockfile_change_invalidates_npm_ci_skip(self):
        with tempfile.TemporaryDirectory(prefix='构见 Q4 bootstrap ') as directory:
            root=make_root(directory);venv_python=root/'.venv/bin/python';venv_python.parent.mkdir(parents=True);venv_python.write_text('')
            runner=Runner();bootstrap.bootstrap(root,python=sys.executable,runner=runner,emit=lambda line:None)
            (root/'package-lock.json').write_text('{"lockfileVersion":3,"changed":true}\n',encoding='utf-8')
            second=bootstrap.bootstrap(root,python=sys.executable,runner=runner,emit=lambda line:None)
            self.assertEqual({a['step']:a['status'] for a in second['actions']}['npm-ci'],'OK')
            self.assertEqual(second['status'],'READY')
    def test_global_interpreter_is_rejected_for_pip(self):
        with tempfile.TemporaryDirectory(prefix='构见 Q4 bootstrap ') as directory:
            venv=Path(directory)/'.venv';target=venv/'bin/python';target.parent.mkdir(parents=True)
            target.symlink_to(Path(sys.executable))
            with self.assertRaisesRegex(bootstrap.BootstrapError,r'outside the isolated \.venv'):
                bootstrap.verify_venv_python(target,venv)
    def test_offline_real_venv_creation_isolation_and_repair(self):
        with tempfile.TemporaryDirectory(prefix='构见 Q4 bootstrap offline ') as directory:
            root=make_root(directory)
            class OfflineRunner:
                def __call__(self,args,cwd=None,env=None,capture_output=False,text=False,**kwargs):
                    if str(args[0]).endswith('npm') or str(args[0]).endswith('npm.cmd'):
                        return SimpleNamespace(returncode=0,stdout='',stderr='')
                    if len(args)>2 and args[1:3]==['-m','pip']:
                        return SimpleNamespace(returncode=0,stdout='',stderr='')
                    if '-c' in args and 'importlib.metadata' in args[args.index('-c')+1]:
                        return SimpleNamespace(returncode=0,stdout='12.1.1\n',stderr='')
                    return subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,**kwargs)
            runner=OfflineRunner()
            first=bootstrap.bootstrap(root,python=sys.executable,runner=runner,emit=lambda line:None)
            self.assertEqual(first['status'],'READY')
            python_path=bootstrap.venv_python(root/'.venv')
            self.assertIsNotNone(python_path)
            probe=subprocess.run([str(python_path),'-c','import json,sys;print(json.dumps({"prefix":sys.prefix,"base":sys.base_prefix}))'],
                                 capture_output=True,text=True,check=True)
            info=json.loads(probe.stdout.strip().splitlines()[-1])
            self.assertEqual(Path(info['prefix']).resolve(),(root/'.venv').resolve())
            self.assertNotEqual(Path(info['prefix']).resolve(),Path(info['base']).resolve())
            second=bootstrap.bootstrap(root,python=sys.executable,runner=runner,emit=lambda line:None)
            self.assertEqual({a['step']:a['status'] for a in second['actions']}['pip-install'],'SKIPPED')
            Path(python_path).unlink()
            third=bootstrap.bootstrap(root,python=sys.executable,runner=runner,emit=lambda line:None)
            self.assertEqual({a['step']:a['status'] for a in third['actions']}['venv'],'OK')
            self.assertEqual(third['status'],'READY')
            self.assertTrue(Path(python_path).exists())

    @unittest.skipUnless(os.environ.get('GOUJIAN_CLEAN_INSTALL')=='1',
                         'set GOUJIAN_CLEAN_INSTALL=1 to run the real npm ci/pip clean-install integration exactly once')
    def test_opt_in_real_clean_install_rerun_and_partial_recovery(self):
        with tempfile.TemporaryDirectory(prefix='goujian clean install ') as directory:
            root=Path(directory)
            for name in ('package.json','package-lock.json','requirements-render.txt'):
                shutil.copy2(ROOT/name,root/name)
            started=time.time()
            first=bootstrap.bootstrap(root,python=sys.executable,emit=lambda line:None)
            self.assertEqual(first['status'],'READY')
            self.assertTrue((root/'node_modules').is_dir())
            self.assertFalse((root/'node_modules').is_symlink())
            self.assertTrue(bootstrap.js_status(root)['ready'])
            python_path=bootstrap.venv_python(root/'.venv')
            self.assertIsNotNone(python_path)
            self.assertTrue(first['pillow'])
            second=bootstrap.bootstrap(root,python=sys.executable,emit=lambda line:None)
            steps={action['step']:action['status'] for action in second['actions']}
            self.assertEqual((steps['npm-ci'],steps['pip-install']),('SKIPPED','SKIPPED'))
            Path(python_path).unlink()
            third=bootstrap.bootstrap(root,python=sys.executable,emit=lambda line:None)
            steps={action['step']:action['status'] for action in third['actions']}
            self.assertEqual((third['status'],steps['venv']),('READY','OK'))
            self.assertTrue(Path(python_path).exists())
            evidence=Path(os.environ.get('GOUJIAN_CLEAN_INSTALL_EVIDENCE',str(ROOT/'out/v12-control/clean-install-evidence.json')))
            evidence.parent.mkdir(parents=True,exist_ok=True)
            evidence.write_text(json.dumps({'status':third['status'],'elapsed_seconds':round(time.time()-started,1),
                'node_modules_symlink':(root/'node_modules').is_symlink(),'dependencies':bootstrap.js_status(root)['installed'],
                'pillow':first['pillow'],'first_actions':first['actions'],'second_actions':second['actions'],
                'third_actions':third['actions'],'scope':'real npm ci and pip install in a temporary copy; rerun skipped both; deleted venv interpreter repaired'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':unittest.main()
