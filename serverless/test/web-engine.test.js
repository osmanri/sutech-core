// The website demo (frontend/demo.html) must run exactly the bot's engine on exactly the bot's demo field.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {DEMO_FIELD, DEMO_WEATHER} from '../tgcloud/lib/demo.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.join(here, '../../frontend/js');
const present = fs.existsSync(path.join(web, 'sutech-engine.js'));

test('website engine is a byte-for-byte copy of the bot engine', {skip: !present && 'frontend submodule not checked out'}, () => {
  assert.equal(fs.readFileSync(path.join(web, 'sutech-engine.js'), 'utf8'), fs.readFileSync(path.join(here, '../tgcloud/lib/balance.js'), 'utf8'),
    'copy serverless/tgcloud/lib/balance.js to frontend/js/sutech-engine.js');
});

test('website demo field and weather equal the bot demo', {skip: !present && 'frontend submodule not checked out'}, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sutech-web-'));
  fs.writeFileSync(path.join(dir, 'package.json'), '{"type":"module"}');
  for (const f of ['sutech-engine.js', 'crops-data.js', 'demo.js']) fs.copyFileSync(path.join(web, f), path.join(dir, f));
  const {DEMO} = await import(pathToFileURL(path.join(dir, 'demo.js')).href);
  for (const k of ['crop', 'soil_type', 'irrigation_type', 'area', 'day_of_growth', 'moisture_condition', 'pump_power_kw', 'pump_productivity_m3h', 'power_price'])
    assert.equal(DEMO[k], DEMO_FIELD[k], k);
  assert.equal(DEMO_FIELD.area_unit, 'hectare');
  assert.equal(DEMO.et0, DEMO_WEATHER.et0);
  assert.equal(DEMO.rain, DEMO_WEATHER.rain);
});

test('website crop files are byte-for-byte copies of the generated ones (crops/build.py)',{skip:!present&&'frontend submodule not checked out'},()=>{
  const same=(a,b,hint)=>assert.equal(fs.readFileSync(a,'utf8'),fs.readFileSync(b,'utf8'),hint);
  same(path.join(web,'crops-data.js'),path.join(here,'../tgcloud/lib/crops-data.js'),'copy serverless/tgcloud/lib/crops-data.js to frontend/js/crops-data.js');
  same(path.join(web,'crops-catalog.js'),path.join(here,'../../crops/crops-catalog.js'),'copy crops/crops-catalog.js to frontend/js/crops-catalog.js');
});
