#!/usr/bin/env python3
"""Environment Doctor: report tool presence, not execution or visual approval."""
import argparse, importlib.util, importlib.metadata, json, os, platform, re, shutil, subprocess, sys, tempfile
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_capabilities():
    spec=importlib.util.spec_from_file_location('goujian_capabilities',ROOT/'core/qa/capabilities.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def load_secure_deps():
    spec=importlib.util.spec_from_file_location('goujian_secure_deps',ROOT/'core/qa/secure_deps.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def parse_version(text):
    match=re.search(r'(\d+)\.(\d+)\.(\d+)',str(text or ''))
    return tuple(int(x) for x in match.groups()) if match else None

def version_text(value):
    return '.'.join(str(x) for x in value) if value else None

class SystemProbe:
    def which(self,name):return shutil.which(name)
    def is_executable(self,path):return bool(path) and os.path.isfile(path) and os.access(path,os.X_OK)
    def run(self,args,timeout=8):
        return subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    def python_version(self):return tuple(sys.version_info[:3])
    def python_executable(self):return sys.executable
    def package_version(self,name):
        path=ROOT/'node_modules'/name/'package.json'
        try:return json.loads(path.read_text(encoding='utf-8')).get('version')
        except (OSError,ValueError):return None
    def pillow_version(self):
        try:return importlib.metadata.version('Pillow'),None
        except importlib.metadata.PackageNotFoundError:return None,None
        except Exception as error:return None,str(error)
    def exists(self,path):return Path(path).exists()
    def venv_python(self,venv):
        candidate=Path(venv)/('Scripts/python.exe' if sys.platform.startswith('win') else 'bin/python')
        return candidate if candidate.is_file() else None
    def venv_pillow_version(self,venv):
        python=self.venv_python(venv)
        if not python:return None
        try:
            result=self.run([str(python),'-c','import importlib.metadata as m; print(m.version("Pillow"))'],timeout=10)
            return result.stdout.strip() if result.returncode==0 else None
        except (OSError,subprocess.TimeoutExpired):return None
    def venv_python_version(self,venv):
        python=self.venv_python(venv)
        if not python:return None
        try:
            result=self.run([str(python),'-c','import sys; print(".".join(map(str,sys.version_info[:3])))'],timeout=10)
            return parse_version(result.stdout) if result.returncode==0 else None
        except (OSError,subprocess.TimeoutExpired):return None
    def can_write(self,path):
        try:
            with tempfile.NamedTemporaryFile(prefix='.goujian-doctor-',dir=path,delete=True) as handle:
                handle.write(b'ok');handle.flush()
            return True,None
        except OSError as error:return False,str(error)
    def platform_info(self):
        current=('win32' if sys.platform.startswith('win') else 'darwin' if sys.platform=='darwin'
                 else 'linux' if sys.platform.startswith('linux') else sys.platform)
        wsl=False
        try:wsl=bool(os.environ.get('WSL_DISTRO_NAME')) or 'microsoft' in Path('/proc/version').read_text(encoding='utf-8').lower()
        except OSError:pass
        return {'system':platform.system(),'release':platform.release(),'machine':platform.machine(),
                'platform':sys.platform,'current':current,'wsl':wsl,
                'wsl_distro':os.environ.get('WSL_DISTRO_NAME')}

def check(**fields):
    base={'id':None,'requirement':'OPTIONAL','status':'MISSING','detected':None,'path':None,
          'detail':'','impact':'','recovery':''}
    base.update(fields);return base

def version_check(probe,identifier,commands,minimum=None,required=True,impact='',recovery=''):
    path=next((probe.which(name) for name in commands if probe.which(name)),None)
    if not path:
        return check(id=identifier,requirement='REQUIRED' if required else 'OPTIONAL',status='MISSING',impact=impact,recovery=recovery)
    if not probe.is_executable(path):
        return check(id=identifier,requirement='REQUIRED' if required else 'OPTIONAL',status='BROKEN',path=path,
                     detail='Command path is not executable',impact=impact,recovery=recovery)
    try:result=probe.run([path,'--version'],timeout=8)
    except (OSError,subprocess.TimeoutExpired) as error:
        return check(id=identifier,requirement='REQUIRED' if required else 'OPTIONAL',status='BROKEN',path=path,
                     detail=str(error),impact=impact,recovery=recovery)
    output=(result.stdout or result.stderr or '').strip().splitlines()
    version=parse_version(output[0] if output else '')
    detected=version_text(version) or (output[0] if output else None)
    if result.returncode!=0 or not version:
        return check(id=identifier,requirement='REQUIRED' if required else 'OPTIONAL',status='BROKEN',path=path,
                     detected=detected,detail='Version command did not return a version',impact=impact,recovery=recovery)
    if minimum and version<minimum:
        return check(id=identifier,requirement='REQUIRED' if required else 'OPTIONAL',status='BROKEN',path=path,
                     detected=detected,detail=f'Requires {version_text(minimum)} or newer',impact=impact,recovery=recovery)
    return check(id=identifier,requirement='REQUIRED' if required else 'OPTIONAL',status='PRESENT',path=path,detected=detected,
                 detail=f'Requires {version_text(minimum)} or newer' if minimum else 'Command found')

def command_check(probe,identifier,commands,required=False,impact='',recovery=''):
    path=next((probe.which(name) for name in commands if probe.which(name)),None)
    requirement='REQUIRED' if required else 'OPTIONAL'
    if not path:return check(id=identifier,requirement=requirement,status='MISSING',impact=impact,recovery=recovery)
    if not probe.is_executable(path):return check(id=identifier,requirement=requirement,status='BROKEN',path=path,detail='Command path is not executable',impact=impact,recovery=recovery)
    return check(id=identifier,requirement=requirement,status='PRESENT',path=path,detected=os.path.basename(path),
                 detail='Command found; execution not verified')

def js_dependency_check(probe,root):
    package_path=Path(root)/'package.json'
    try:package=json.loads(package_path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:
        return check(id='js-dependencies',requirement='REQUIRED',status='BROKEN',detail=f'Cannot read package.json: {error}',
                     impact='Deck build and validation unavailable',recovery='Restore package.json and run npm run bootstrap')
    expected={**package.get('dependencies',{}),**package.get('overrides',{})}
    installed,missing,mismatched={},[],[]
    for name,wanted in sorted(expected.items()):
        actual=probe.package_version(name)
        installed[name]=actual
        if not actual:missing.append(name)
        elif wanted and re.fullmatch(r'\d+\.\d+\.\d+',str(wanted)) and actual!=wanted:mismatched.append(f'{name} {actual}!={wanted}')
    if missing or mismatched:
        detail='; '.join((['missing '+', '.join(missing)] if missing else [])+(['version mismatch '+', '.join(mismatched)] if mismatched else []))
        return check(id='js-dependencies',requirement='REQUIRED',status='MISSING' if missing else 'BROKEN',detected=installed,detail=detail,
                     impact='Build, schema validation and analytics unavailable',recovery='Run npm run bootstrap (npm ci from package-lock.json)')
    return check(id='js-dependencies',requirement='REQUIRED',status='PRESENT',detected=installed,detail='Exact dependency versions installed')

def font_check(probe):
    fc_list,fc_match=probe.which('fc-list'),probe.which('fc-match')
    if not fc_list or not fc_match:
        return check(id='fonts',requirement='OPTIONAL',status='MISSING',
                     impact='Font inventory, CJK/bold substitution checks and reliable visual review',
                     recovery='Install fontconfig and a CJK font such as Noto Sans CJK SC (OS package manager)')
    try:
        normal=probe.run([fc_match,'-f','%{family}|%{style}\n','Noto Sans CJK SC'],timeout=8)
        bold=probe.run([fc_match,'-f','%{family}|%{style}\n','Noto Sans CJK SC:bold'],timeout=8)
    except (OSError,subprocess.TimeoutExpired) as error:
        return check(id='fonts',requirement='OPTIONAL',status='BROKEN',detail=str(error),
                     impact='Font inventory and substitution checks unavailable',recovery='Repair fontconfig, then rerun npm run doctor')
    normal_text=(normal.stdout or '').strip().splitlines()[0] if normal.returncode==0 and normal.stdout.strip() else ''
    bold_text=(bold.stdout or '').strip().splitlines()[0] if bold.returncode==0 and bold.stdout.strip() else ''
    family=normal_text.split('|')[0].strip();style=normal_text.split('|')[-1].strip()
    bold_family=bold_text.split('|')[0].strip();bold_style=bold_text.split('|')[-1].strip()
    cjk_keywords=('cjk','source han','noto sans sc','wenquanyi','pingfang','microsoft yahei','simsun','droid sans fallback')
    cjk_ok=any(keyword in family.lower() for keyword in cjk_keywords)
    bold_ok='bold' in bold_style.lower() and any(keyword in bold_family.lower() for keyword in cjk_keywords)
    detected={'requested':'Noto Sans CJK SC','matched_family':family,'matched_style':style,
              'bold_family':bold_family,'bold_style':bold_style,'fc_list':fc_list,'fc_match':fc_match}
    if cjk_ok and bold_ok:
        return check(id='fonts',requirement='OPTIONAL',status='PRESENT',detected=detected,
                     detail='fc-match family heuristic found a CJK family and bold style; glyph coverage is not verified')
    return check(id='fonts',requirement='OPTIONAL',status='BROKEN',detected=detected,
                 detail='fc-match family heuristic did not match CJK or CJK bold; rendered text may be substituted; glyph coverage is not verified',
                 impact='CJK/bold substitution checks and reliable visual review',
                 recovery='Install Noto Sans CJK SC with bold weight, then rerun npm run doctor')

def writable_check(probe,identifier,path):
    ok,error=probe.can_write(path)
    if ok:return check(id=identifier,requirement='REQUIRED',status='PRESENT',path=str(path),detail='Write probe succeeded')
    return check(id=identifier,requirement='REQUIRED',status='BROKEN',path=str(path),detail=error or 'Write probe failed',
                 impact='Build output and temporary asset processing unavailable',recovery='Choose a writable working directory or fix permissions')

def platform_check(probe):
    info=probe.platform_info();current=info['current']
    supported={'linux','darwin','win32'}
    status='PRESENT' if current in supported else 'UNSUPPORTED'
    info['support']={name:('AVAILABLE' if name==current else 'NOT_RUN') for name in ['linux','darwin','win32']}
    return check(id='platform',requirement='REQUIRED',status=status,detected=info,
                 detail='WSL detected' if info.get('wsl') else ('Unrecognized platform reported without normalization' if status=='UNSUPPORTED' else 'Native platform'),
                 impact='Unexecuted platforms are NOT_RUN, not verified',recovery='Run npm run doctor on the target platform')

def inspect(probe=None):
    probe=probe or SystemProbe()
    root=Path(ROOT)
    secure_deps=load_secure_deps()
    checks=[]
    checks.append(platform_check(probe))
    checks.append(version_check(probe,'node',['node'],minimum=(18,0,0),impact='Deck build unavailable',recovery='Install Node.js 18+'))
    checks.append(version_check(probe,'npm',['npm','npm.cmd'],impact='Dependency bootstrap unavailable',
                                recovery='Install Node.js 18+ (includes npm); if Node/npm is installed later, run python3 scripts/bootstrap.py directly'))
    python=probe.python_version();python_tuple=tuple(python[:3]) if python else None
    secure_python=secure_deps.MIN_PYTHON_SECURE
    if not python_tuple or python_tuple<(3,9):
        checks.append(check(id='python',requirement='REQUIRED',status='BROKEN',detected=version_text(python_tuple),
                            detail=f'Requires {version_text((3,9,0))} or newer',impact='Validation, QA and asset scripts unavailable',
                            recovery='Use Python 3.9+ for the core tier, or Python 3.11+ for the secure image/render tier; set GOUJIAN_PYTHON during bootstrap'))
    elif python_tuple<secure_python:
        checks.append(check(id='python',requirement='REQUIRED',status='PRESENT',path=probe.python_executable(),
                            detected=version_text(python_tuple),
                            detail=f'Core tier only: secure image/render tier requires {version_text(secure_python)}+'))
    else:
        checks.append(check(id='python',requirement='REQUIRED',status='PRESENT',path=probe.python_executable(),
                            detected=version_text(python_tuple),
                            detail=f'Core tier {version_text((3,9,0))}+ and secure image/render tier {version_text(secure_python)}+'))
    checks.append(js_dependency_check(probe,root))
    venv=root/'.venv';venv_python=probe.venv_python(venv) if probe.exists(venv) else None
    venv_pillow=probe.venv_pillow_version(venv) if venv_python else None
    venv_python_version=probe.venv_python_version(venv) if venv_python else None
    if not probe.exists(venv):
        checks.append(check(id='venv',requirement='OPTIONAL',status='MISSING',path=str(venv),detected=None,
                            impact='Dependencies are not isolated; system Python is used',recovery='Run npm run bootstrap'))
    elif not venv_python:
        checks.append(check(id='venv',requirement='OPTIONAL',status='BROKEN',path=str(venv),
                            impact='Dependencies are not isolated; system Python is used',recovery='Rerun npm run bootstrap to repair .venv'))
    else:
        checks.append(check(id='venv',requirement='OPTIONAL',status='PRESENT',path=str(venv_python),
                            detected={'python':version_text(venv_python_version),'pillow':venv_pillow},
                            detail='Isolated virtual environment found'))
    pillow,error=probe.pillow_version()
    pillow_secure=secure_deps.pillow_is_secure(pillow)
    if pillow and pillow_secure:
        checks.append(check(id='pillow',requirement='OPTIONAL',status='PRESENT',detected=pillow,
                            detail=f'Active interpreter has Pillow {pillow} (secure tier)'))
    elif pillow:
        checks.append(check(id='pillow',requirement='OPTIONAL',status='BROKEN',detected=pillow,
                            detail=f'Pillow {pillow} is affected by published advisories and is unsafe for untrusted image processing',
                            impact='Untrusted raster preparation and secure image rendering unavailable; core spec/geometry/PPTX inspection remains available',
                            recovery=f'Recreate .venv with Python {version_text(secure_python)}+ and install requirements-render.txt (Pillow {secure_deps.version_text(secure_deps.MIN_PILLOW)}); never install an older vulnerable Pillow fallback'))
    elif error:
        checks.append(check(id='pillow',requirement='OPTIONAL',status='BROKEN',detected=error,
                            impact='Asset preparation and PNG rendering unavailable',
                            recovery='Activate .venv or run npm run bootstrap to install Pillow in isolation'))
    else:
        checks.append(check(id='pillow',requirement='OPTIONAL',status='MISSING',
                            detail='Core tier does not require Pillow',
                            impact='Untrusted raster preparation and secure image rendering unavailable; core spec/geometry/PPTX inspection remains available',
                            recovery=f'Optional: run npm run bootstrap with Python {version_text(secure_python)}+ to install the secure image tier'))
    effective_python=venv_python_version or python_tuple
    effective_pillow=venv_pillow if venv_python else pillow
    secure_status=secure_deps.secure_image_status(python=effective_python,pillow=effective_pillow)
    if secure_status['status']=='AVAILABLE':
        checks.append(check(id='secure-image',requirement='OPTIONAL',status='PRESENT',
                            detected={'runtime':'venv' if venv_python else 'active',**secure_status},
                            detail=f"Secure image/render tier available: {secure_status['reason']}"))
    else:
        checks.append(check(id='secure-image',requirement='OPTIONAL',
                            status='BROKEN' if secure_status['status']=='INSECURE' else 'MISSING',
                            detected={'runtime':'venv' if venv_python else 'active',**secure_status},
                            detail=secure_status['reason'],
                            impact='Untrusted raster preparation and native render/montage unavailable; core spec/geometry/PPTX inspection remains available',
                            recovery=(f'Use Python {secure_status["min_python"]}+ and install requirements-render.txt (Pillow {secure_status["min_pillow"]}) in an isolated .venv; never fall back to an older vulnerable Pillow'
                                      if secure_status['status']=='INSECURE' else
                                      f'Optional: run npm run bootstrap with Python {secure_status["min_python"]}+ to install the secure image tier')))
    checks.append(command_check(probe,'libreoffice',['libreoffice','soffice'],
                                impact='Native rendering and visual review unavailable',
                                recovery='Install LibreOffice (OS package manager); PPTX inspection still works'))
    checks.append(command_check(probe,'poppler',['pdftoppm'],
                                impact='PDF-to-PNG rendering and visual review unavailable',
                                recovery='Install Poppler utilities (OS package manager)'))
    checks.append(font_check(probe))
    checks.append(writable_check(probe,'cwd-writable',os.getcwd()))
    checks.append(writable_check(probe,'temp-writable',tempfile.gettempdir()))
    python_ready=next(item['status']=='PRESENT' for item in checks if item['id']=='python')
    capabilities=load_capabilities().detect(probe=probe,python_ready=python_ready,secure_status=secure_status)
    required_missing=[item for item in checks if item['requirement']=='REQUIRED' and item['status']!='PRESENT']
    optional_gaps=[item for item in checks if item['requirement']=='OPTIONAL' and item['status']!='PRESENT']
    status='BLOCKED' if required_missing else ('READY_WITH_NOTES' if optional_gaps else 'READY')
    result={'status':status,'generated_at':datetime.now().astimezone().isoformat(timespec='seconds'),
            'platform':next(item['detected'] for item in checks if item['id']=='platform'),
            'checks':checks,
            'summary':{'required_ok':sum(1 for item in checks if item['requirement']=='REQUIRED' and item['status']=='PRESENT'),
                       'required_total':sum(1 for item in checks if item['requirement']=='REQUIRED'),
                       'optional_gaps':len(optional_gaps),'blocked':bool(required_missing)},
            'capabilities':capabilities,
            'visual_qa':capabilities['VISUAL_QA'],
            'note':'Doctor reports presence/version only. Command execution and visual review are never approved automatically.'}
    return result

def human(result):
    lines=[f"Goujian Environment Doctor: {result['status']}",
           f"Platform: {result['platform']['system']} {result['platform']['machine']} ({result['platform']['current']})"+
           (f" · WSL {result['platform'].get('wsl_distro') or ''}".rstrip() if result['platform'].get('wsl') else ''),
           f"Platforms: "+' · '.join(f"{k}={v}" for k,v in result['platform']['support'].items())]
    for item in result['checks']:
        detected=f" {item['detected']}" if isinstance(item['detected'],(str,int,float)) and item['detected'] else ''
        lines.append(f"[{item['status']}] {item['requirement']} {item['id']}{detected}")
    ladder=result['capabilities']['ladder']
    lines.append('Capabilities: '+' · '.join(f"{name}={value['status']}" for name,value in ladder.items()))
    lines.append(f"Visual QA: {result['visual_qa']} (reviewer attestation required; never automatic)")
    for item in result['checks']:
        if item['requirement']=='OPTIONAL' and item['status']!='PRESENT':
            lines.append(f"Optional gap: {item['id']} {item['status']} — {item['impact'] or item['detail']}; recovery: {item['recovery']}")
    for item in result['checks']:
        if item['requirement']=='REQUIRED' and item['status']!='PRESENT':
            lines.append(f"Required failure: {item['id']} {item['status']} — {item['impact'] or item['detail']}; recovery: {item['recovery']}")
    return '\n'.join(lines)

def main():
    parser=argparse.ArgumentParser(description='Report required/optional environment capabilities.')
    parser.add_argument('--json',action='store_true',help='Print machine-readable JSON only')
    args=parser.parse_args()
    result=inspect()
    print(json.dumps(result,ensure_ascii=False,indent=2) if args.json else human(result))
    raise SystemExit(1 if result['status']=='BLOCKED' else 0)

if __name__=='__main__':main()
