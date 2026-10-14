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

function resolveProfileFile(ref, repoRoot) {
  const id = ref || 'executive-clean';
  const direct = path.resolve(id);
  if (fs.existsSync(direct) && fs.statSync(direct).isFile()) return direct;
  for (const dir of profileSearchDirs(repoRoot)) {
    for (const p of [path.join(dir, id, 'profile.json'), path.join(dir, `${id}.json`)]) {
      if (fs.existsSync(p) && fs.statSync(p).isFile()) return p;
    }
  }
  throw new Error(`profile not found: ${id}`);
}

function loadProfile(profileRef, repoRoot, seen = new Set()) {
  const base = repoRoot || path.resolve(__dirname, '../..');
  const file = resolveProfileFile(profileRef || 'executive-clean', base);
  const key = path.resolve(file);
  if (seen.has(key)) throw new Error(`profile inheritance cycle: ${key}`);
  seen.add(key);
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!data.extends) return data;
  const relativeParent = path.resolve(path.dirname(file), data.extends);
  const parent = loadProfile(fs.existsSync(relativeParent) ? relativeParent : data.extends, base, seen);
  const child = Object.assign({}, data); delete child.extends;
  return deepMerge(parent, child);
}

module.exports = { loadProfile, deepMerge, profileSearchDirs };
