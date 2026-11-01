import {writeFileSync, readFileSync} from 'node:fs';
import {missionMessages} from '../i18n.js';
const languages={it:{},en:{}};
for(const [key,values] of Object.entries(missionMessages)){
  if(values.length!==2||values.some(value=>!value))throw new Error(`Missing mission translation: ${key}`);
  languages.it[key]=values[0];languages.en[key]=values[1];
}
const path=new URL('../desktop/mission_i18n.json',import.meta.url);
const data=JSON.stringify(languages,null,2)+'\n';
if(process.argv.includes('--check')){
  if(readFileSync(path,'utf8')!==data)throw new Error('Run node tools/export_mission_i18n.mjs to refresh native translations');
}else writeFileSync(path,data);
console.log(`Mission i18n: ${Object.keys(missionMessages).length} keys, IT/EN, native dictionary ${process.argv.includes('--check')?'verified':'exported'}`);
