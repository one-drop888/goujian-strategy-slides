#!/usr/bin/env python3
"""Idempotent local bootstrap: npm ci from the lockfile plus an isolated .venv."""
import argparse, hashlib, importlib.util, json, os, platform, re, shutil, subprocess, sys, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class BootstrapError(RuntimeError):pass

def read_json(path,default=None):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def run_command(args,cwd,env=None,runner=None):
    runner=runner or subprocess.run
    return runner(args,cwd=str(cwd),env=env,capture_output=True,text=True)

def version_tuple(text):
    match=re.search(r'(\d+)\.(\d+)\.(\d+)',str(text or ''))
    return tuple(int(x) for x in match.groups()) if match else None

def load_secure_deps():
    spec=importlib.util.spec_from_file_location('goujian_secure_deps',ROOT/'core/qa/secure_deps.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def python_candidates():
    seen=set()
    for name in ('python3.14','python3.13','python3.12','python3.11','python3','python'):
        path=shutil.which(name)
        if path and path not in seen:
            seen.add(path);yield path

def choose_python(explicit=None,runner=None):
    secure_deps=load_secure_deps()
    if explicit:return explicit,'--python (explicit selection)'
    if os.environ.get('GOUJIAN_PYTHON'):return os.environ['GOUJIAN_PYTHON'],'GOUJIAN_PYTHON (explicit selection)'
    if tuple(sys.version_info[:3])>=secure_deps.MIN_PYTHON_SECURE:
        return sys.executable,f"current interpreter (Python >= {secure_deps.version_text(secure_deps.MIN_PYTHON_SECURE)})"
    for path in python_candidates():
        try:version=version_tuple(verify_python(path,runner))
        except BootstrapError:continue
        if version>=secure_deps.MIN_PYTHON_SECURE:
            return path,f"PATH fallback (Python >= {secure_deps.version_text(secure_deps.MIN_PYTHON_SECURE)} found; current interpreter is older)"
    if tuple(sys.version_info[:3])>=(3,9):
        current=version_tuple('.'.join(map(str,tuple(sys.version_info[:3]))))
        raise BootstrapError(
            f'Secure bootstrap requires Python >= {secure_deps.version_text(secure_deps.MIN_PYTHON_SECURE)}; '
            f'the current interpreter is {secure_deps.version_text(current)} and no newer interpreter was found. '
            f'Install Python {secure_deps.version_text(secure_deps.MIN_PYTHON_SECURE)}+, or pass --python to opt into the core-only tier '
            f'(Pillow is never installed for Python < {secure_deps.version_text(secure_deps.MIN_PYTHON_SECURE)}).')
    raise BootstrapError(f'Python >= 3.9 not found; install Python 3.9+ (3.11+ for the secure image/render tier) or pass --python')

def verify_python(path,runner=None):
    result=run_command([path,'-c','import sys; print(".".join(map(str,sys.version_info[:3])))'],Path.cwd(),runner=runner)
    version=version_tuple(result.stdout if result.returncode==0 else '')
    if result.returncode!=0 or not version:raise BootstrapError(f'Cannot execute Python at {path}: {(result.stderr or result.stdout).strip()}')
    if version<(3,9):raise BootstrapError(f'Python >= 3.9 required; {path} is {version[0]}.{version[1]}.{version[2]}')
    return '.'.join(map(str,version))

def expected_js(root):
    package=read_json(Path(root)/'package.json')
    if not package:raise BootstrapError('package.json not found or invalid')
    return {**package.get('dependencies',{}),**package.get('overrides',{})}

def js_status(root):
    installed,missing,mismatched={},[],[]
    for name,wanted in sorted(expected_js(root).items()):
        package=read_json(Path(root)/'node_modules'/name/'package.json')
        actual=package.get('version') if package else None
        installed[name]=actual
        if not actual:missing.append(name)
        elif re.fullmatch(r'\d+\.\d+\.\d+',str(wanted)) and actual!=wanted:mismatched.append(f'{name} {actual}!={wanted}')
    return {'ready':not missing and not mismatched,'installed':installed,'missing':missing,'mismatched':mismatched}

def npm_command():
    return shutil.which('npm') or shutil.which('npm.cmd')

def venv_python(venv):
    candidate=Path(venv)/('Scripts/python.exe' if platform.system()=='Windows' else 'bin/python')
    return candidate if candidate.is_file() else None

def python_inside_venv(venv,python):
    try:Path(os.path.abspath(str(python))).relative_to(Path(os.path.abspath(str(venv))));return True
    except ValueError:return False

def verify_venv_python(python,venv,runner=None):
    """The Unix venv interpreter is a symlink to the base runtime, so validate
    the executed interpreter's sys.prefix rather than the symlink target."""
    probe=run_command([str(python),'-c',
        'import json,sys;print(json.dumps({"prefix":sys.prefix,"base":sys.base_prefix}))'],Path.cwd(),runner=runner)
    if probe.returncode!=0:raise BootstrapError(f'Cannot execute isolated Python at {python}: {(probe.stderr or probe.stdout).strip()}')
    try:info=json.loads(probe.stdout.strip().splitlines()[-1])
    except (ValueError,IndexError):raise BootstrapError(f'Isolated Python at {python} did not report sys.prefix')
    prefix=Path(info.get('prefix','')).resolve();base=Path(info.get('base','')).resolve()
    if prefix!=Path(venv).resolve() or prefix==base:
        raise BootstrapError(f'Refusing pip outside the isolated .venv: {python} reports sys.prefix={prefix}')
    if not python_inside_venv(venv,python):
        raise BootstrapError(f'Refusing pip outside the isolated .venv: {python}')
    return info

def verify_venv_version(python,runner=None):
    result=run_command([str(python),'-c','import sys; print(".".join(map(str,sys.version_info[:3])))'],Path.cwd(),runner=runner)
    version=version_tuple(result.stdout if result.returncode==0 else '')
    if result.returncode!=0 or not version:
        raise BootstrapError(f'Cannot read the isolated Python version at {python}: {(result.stderr or result.stdout).strip()}')
    return version

def venv_pillow(python,runner=None):
    result=run_command([str(python),'-c','import importlib.metadata as m; print(m.version("Pillow"))'],Path.cwd(),runner=runner)
    return result.stdout.strip() if result.returncode==0 else None

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def state_path(venv):return Path(venv)/'.goujian-bootstrap.json'

def read_state(venv):return read_json(state_path(venv),{})

def write_state(venv,state):
    target=state_path(venv);temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,target)

def bootstrap(root=ROOT,python=None,dry_run=False,force=False,runner=None,emit=print):
    root=Path(root).resolve();runner=runner or subprocess.run
    secure_deps=load_secure_deps()
    explicit=bool(python or os.environ.get('GOUJIAN_PYTHON'))
    selected,reason=choose_python(python,runner)
    python_version=verify_python(selected,runner)
    selected_version=version_tuple(python_version)
    actions=[]
    requirements=root/'requirements-render.txt'
    if not requirements.is_file():raise BootstrapError('requirements-render.txt is required for the isolated environment')
    requirement_errors=secure_deps.validate_requirements_text(requirements.read_text(encoding='utf-8'))
    if requirement_errors:raise BootstrapError('; '.join(requirement_errors))
    venv=root/'.venv'
    state=read_state(venv) if venv.is_dir() else {}
    lockfile=root/'package-lock.json'
    lock_hash=file_hash(lockfile) if lockfile.is_file() else None
    # 1. JavaScript dependencies from the lockfile. Skip only when the last
    # successful npm-ci used this exact lockfile; top-level versions alone are
    # insufficient because transitives may have changed.
    status=js_status(root)
    js_state_current=(state.get('npm_ready') is True and state.get('lock_sha256') is not None
                      and state.get('lock_sha256')==lock_hash)
    if status['ready'] and js_state_current and not force:
        actions.append({'step':'npm-ci','status':'SKIPPED','reason':'exact dependency versions installed for this lockfile hash'})
    else:
        npm=npm_command()
        if not npm:raise BootstrapError('npm not found; install Node.js 18+ (includes npm), then rerun python3 scripts/bootstrap.py')
        if not lockfile.is_file():raise BootstrapError('package-lock.json is required for npm ci')
        command=[npm,'ci','--no-audit','--no-fund']
        if dry_run:actions.append({'step':'npm-ci','status':'PLANNED','command':command})
        else:
            result=run_command(command,root,runner=runner)
            if result.returncode!=0:raise BootstrapError(f'npm ci failed: {(result.stderr or result.stdout).strip()}')
            status=js_status(root)
            if not status['ready']:
                raise BootstrapError('npm ci completed but required JS dependencies are missing or mismatched: '
                                     + ', '.join(status['missing']+status['mismatched']))
            actions.append({'step':'npm-ci','status':'OK','command':command})
    js_ready=status['ready']
    # 2. Isolated virtual environment (repairing an interrupted partial venv is safe).
    python_path=venv_python(venv)
    if python_path:
        if not dry_run:
            verify_venv_python(python_path,venv,runner)
            venv_version=verify_venv_version(python_path,runner)
            if explicit and venv_version[:2]!=selected_version[:2]:
                raise BootstrapError(
                    f'Explicit Python selection {python_version} does not match the existing .venv interpreter '
                    f'{secure_deps.version_text(venv_version)}. Use a matching --python or move the existing .venv aside, then rerun bootstrap.')
            python_version=secure_deps.version_text(venv_version)
            selected_version=venv_version
        actions.append({'step':'venv','status':'SKIPPED','path':str(venv),'reason':'virtual environment already present'})
    else:
        command=[selected,'-m','venv',str(venv)]
        if dry_run:actions.append({'step':'venv','status':'PLANNED','command':command})
        else:
            result=run_command(command,root,runner=runner)
            if result.returncode!=0:raise BootstrapError(f'venv creation failed: {(result.stderr or result.stdout).strip()}')
            python_path=venv_python(venv)
            if not python_path:raise BootstrapError('venv created without a Python interpreter; rerun bootstrap')
            verify_venv_python(python_path,venv,runner)
            python_version=secure_deps.version_text(verify_venv_version(python_path,runner))
            selected_version=version_tuple(python_version)
            actions.append({'step':'venv','status':'OK','path':str(python_path)})
    tier='secure' if selected_version>=secure_deps.MIN_PYTHON_SECURE else 'core'
    if tier!='secure' and not explicit:
        raise BootstrapError(
            f'Existing .venv uses Python {python_version}, but the secure image/render tier requires '
            f'{secure_deps.version_text(secure_deps.MIN_PYTHON_SECURE)}+. Move .venv aside and rerun bootstrap, or pass --python '
            f'to explicitly choose the core-only tier (Pillow is not installed then).')
    requirement_hash=file_hash(requirements)
    pillow=venv_pillow(python_path,runner) if python_path else None
    if tier=='core':
        actions.append({'step':'pip-install','status':'SKIPPED','reason':
                        f'explicit Python {python_version} (< {secure_deps.version_text(secure_deps.MIN_PYTHON_SECURE)}): core-only tier; no Pillow install and no vulnerable fallback'})
    else:
        state_matches=(state.get('requirements_sha256')==requirement_hash and state.get('lock_sha256')==lock_hash
                       and state.get('python_version')==python_version and state.get('npm_ready') is True and js_ready
                       and state.get('tier')=='secure' and secure_deps.pillow_is_secure(pillow))
        # 3. Isolated Python dependencies, never global pip.
        if state_matches and not force:
            actions.append({'step':'pip-install','status':'SKIPPED','reason':'bootstrap state is complete and requirements are unchanged','pillow':pillow})
        else:
            planned_python=python_path or venv_python(venv)
            if planned_python is None and dry_run:
                suffix='Scripts/python.exe' if platform.system()=='Windows' else 'bin/python'
                planned_python=venv/suffix
            if planned_python is None:raise BootstrapError('virtual environment Python is unavailable')
            if not python_inside_venv(venv,planned_python):
                raise BootstrapError('Refusing pip outside the isolated .venv')
            if not dry_run:verify_venv_python(planned_python,venv,runner)
            command=[str(planned_python),'-m','pip','install','--disable-pip-version-check','--no-input','-r',str(requirements)]
            env={**os.environ,'PYTHONNOUSERSITE':'1','PIP_NO_INPUT':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1','PIP_USER':'0'}
            if dry_run:actions.append({'step':'pip-install','status':'PLANNED','command':command,'env':{'PYTHONNOUSERSITE':'1'}})
            else:
                result=run_command(command,root,env=env,runner=runner)
                if result.returncode!=0:raise BootstrapError(f'pip install failed: {(result.stderr or result.stdout).strip()}')
                pillow=venv_pillow(planned_python,runner)
                if not secure_deps.pillow_is_secure(pillow):
                    raise BootstrapError(
                        f'pip install completed but the isolated .venv has Pillow {pillow or "missing"}; '
                        f'secure Pillow {secure_deps.version_text(secure_deps.MIN_PILLOW)} is required for Python {python_version}. '
                        f'Check that pip resolves the python_version marker in requirements-render.txt.')
                actions.append({'step':'pip-install','status':'OK','command':command,'pillow':pillow})
    if not dry_run:
        state={'schema_version':2,'tier':tier,'secure_image':'AVAILABLE' if tier=='secure' else 'UNAVAILABLE',
               'completed_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
               'python':str(selected),'python_version':python_version,'venv_python':str(python_path or venv_python(venv)),
               'requirements_sha256':requirement_hash,'lock_sha256':lock_hash,'npm_ready':js_ready,'pillow':pillow}
        write_state(venv,state)
        actions.append({'step':'state','status':'OK','path':str(state_path(venv))})
    result={'status':'DRY_RUN' if dry_run else 'READY','root':str(root),'python':str(selected),
            'python_choice':reason,'python_version':python_version,'tier':tier,
            'secure_image':'AVAILABLE' if tier=='secure' else 'UNAVAILABLE','venv':str(venv),'pillow':pillow,'actions':actions}
    emit_human(result,emit)
    return result

def emit_human(result,emit):
    emit(f"Bootstrap: {result['status']}")
    emit(f"Root: {result['root']}")
    emit(f"Python: {result['python']} ({result['python_choice']}, {result['python_version']})")
    emit(f"Tier: {result['tier']} (secure image/render: {result['secure_image']})")
    for action in result['actions']:
        detail=action.get('reason') or action.get('path') or ' '.join(action.get('command',[]))
        emit(f"- {action['step']}: {action['status']} {detail}")
    if result['status']!='DRY_RUN':
        activate=Path(result['venv'])/('Scripts/activate' if platform.system()=='Windows' else 'bin/activate')
        emit(f"Activate isolated dependencies: source {activate}" if platform.system()!='Windows' else f"Activate isolated dependencies: {activate}")

def main():
    parser=argparse.ArgumentParser(description='Install npm and Python dependencies locally without sudo.')
    parser.add_argument('--root',default=str(ROOT),help='Project root (defaults to repository root)')
    parser.add_argument('--python',help='Python interpreter to create .venv (defaults to GOUJIAN_PYTHON or the current >=3.9 interpreter)')
    parser.add_argument('--dry-run',action='store_true',help='Show actions without creating files or downloading')
    parser.add_argument('--force',action='store_true',help='Reinstall even when dependency state matches')
    parser.add_argument('--json',action='store_true',help='Print machine-readable JSON')
    args=parser.parse_args()
    try:
        if args.json:
            result=None
            def capture(line):pass
            result=bootstrap(Path(args.root),args.python,args.dry_run,args.force,emit=capture)
            print(json.dumps(result,ensure_ascii=False,indent=2))
        else:
            bootstrap(Path(args.root),args.python,args.dry_run,args.force)
    except BootstrapError as error:
        if args.json:print(json.dumps({'status':'FAILED','error':str(error)},ensure_ascii=False,indent=2))
        else:print(f'Bootstrap failed: {error}',file=sys.stderr)
        raise SystemExit(1)

if __name__=='__main__':main()
