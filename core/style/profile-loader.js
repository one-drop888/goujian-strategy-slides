const fs = require('fs');
const path = require('path');

function isObject(v) { return v && typeof v === 'object' && !Array.isArray(v); }
function deepMerge(base, override) {
  const out = Object.assign({}, base || {});
  for (const [k,v] of Object.entries(override || {})) {
    out[k] = isObject(v) && isObject(out[k]) ? deepMerge(out[k], v) : v;
  }
  return out;
}

function profileSearchDirs(repoRoot) {
  const envDirs = (process.env.PRESENTATION_PROFILE_DIRS || '')
    .split(path.delimiter).map(x => x.trim()).filter(Boolean);
  return [path.join(repoRoot, 'skill', 'profiles'), ...envDirs];
}

function resolveProfileFile(ref, repoRoot, projectDir) {
  const id = ref || 'executive-clean';
  const configured=profileSearchDirs(repoRoot);
  const dirs=[configured[0],...(projectDir?[path.join(projectDir,'profiles'),projectDir]:[]),...configured.slice(1)];
  for (const dir of dirs) {
    for (const p of [path.join(dir, id, 'profile.json'), path.join(dir, `${id}.json`)]) {
      if (fs.existsSync(p) && fs.statSync(p).isFile()) return p;
    }
  }
  const direct = path.resolve(projectDir||process.cwd(),id);
  if (fs.existsSync(direct) && fs.statSync(direct).isFile()) return direct;
  throw new Error(`profile not found: ${id}`);
}

function loadProfile(profileRef, repoRoot, seen = new Set(), projectDir) {
  const base = repoRoot || path.resolve(__dirname, '../..');
  const file = resolveProfileFile(profileRef || 'executive-clean', base,projectDir);
  const key = path.resolve(file);
  if (seen.has(key)) throw new Error(`profile inheritance cycle: ${key}`);
  seen.add(key);
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!data.extends) return data;
  const relativeParent = path.resolve(path.dirname(file), data.extends);
  const parent = loadProfile(fs.existsSync(relativeParent) ? relativeParent : data.extends, base, seen,projectDir);
  const child = Object.assign({}, data); delete child.extends;
  return deepMerge(parent, child);
}

function profileChain(profileRef, repoRoot, projectDir) {
  const base = repoRoot || path.resolve(__dirname, '../..');
  const files = [], seen = new Set();
  function visit(ref) {
    const file = resolveProfileFile(ref, base, projectDir);
    const key = fs.realpathSync(file);
    if (seen.has(key)) throw new Error(`profile inheritance cycle: ${key}`);
    seen.add(key);
    files.push(file);
    const data = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (!data.extends) return;
    const relativeParent = path.resolve(path.dirname(file), data.extends);
    visit(fs.existsSync(relativeParent) ? relativeParent : data.extends);
  }
  visit(profileRef || 'executive-clean');
  return files;
}

module.exports = { loadProfile, profileChain, deepMerge, profileSearchDirs, resolveProfileFile };
