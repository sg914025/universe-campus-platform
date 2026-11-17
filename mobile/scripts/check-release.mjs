// Author: UniVerse Team. Readiness check only; no upload or publication.
import fs from 'node:fs';
const c=JSON.parse(fs.readFileSync(new URL('../config/project.json',import.meta.url),'utf8').replace(/^\uFEFF/,''));
const issues=[];
if(!c.apiBase.startsWith('https://')||/localhost|127\.0\.0\.1/.test(c.apiBase))issues.push('Set apiBase to your public HTTPS backend.');
if(!c.wechatAppId)issues.push('Set your own WeChat mini-program AppID.');
if(!c.dcloudAppId)issues.push('Set your own DCloud AppID before native packaging.');
console.log(issues.length?issues.join('\n'):'Configuration is ready for platform verification.');
console.log('WeChat domains, privacy declarations, camera/location access and Android/iOS signing are verified in their official consoles. This script does not publish anything.');
process.exitCode=issues.length?1:0;
