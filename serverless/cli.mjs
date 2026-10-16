// Local deployment helper. Credentials stay in ignored bot/.env and child env.
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root = fileURLToPath(new URL('.', import.meta.url));
const env = {...process.env};
for (const line of fs.readFileSync(new URL('../bot/.env', import.meta.url), 'utf8').split(/\r?\n/)) {
  const match = line.match(/^([A-Z_]+)=(.*)$/);
  if (match && !env[match[1]]) env[match[1]] = match[2].trim().replace(/^['"]|['"]$/g, '');
}
delete env.TGCLOUD_DEBUG;
delete env.TG_CLOUD_API_URL;
const secrets = Object.entries(env).filter(([k,v]) => v && /TOKEN|SECRET|API_KEY|DATABASE_URL/.test(k)).map(([,v])=>v);
const result = spawnSync(process.execPath, [root+'node_modules/@tgcloud/cli/bin/tgcloud.js', ...process.argv.slice(2)], {cwd:root, env, encoding:'utf8', timeout:120000, maxBuffer:8*1024*1024});
let output = (result.stdout || '') + (result.stderr || '');
for (const secret of secrets) output = output.split(secret).join('<REDACTED>');
output = output.replace(/app\d+:[A-Za-z0-9_-]{20,}/g, '<REDACTED>');
process.stdout.write(output);
if (result.error) console.error(result.error.code || 'CLI_PROCESS_FAILED');
process.exit(result.status ?? 1);
