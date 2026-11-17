// Shared build entry. Author: UniVerse Team.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=file=>JSON.parse(fs.readFileSync(path.join(root,file),'utf8').replace(/^\uFEFF/,''));
const config=read('config/project.json');
const backend=path.resolve(root,process.env.UNIVERSE_BACKEND_PATH||config.backendPath);
const modes={web:[],weixin:['-p','mp-weixin'],app:['-p','app']};
const chosen=process.argv[2]||'all';
if(chosen!=='all'&&!modes[chosen])throw new Error('Use all, web, weixin or app.');
const api=new URL(config.apiBase);
if(!['http:','https:'].includes(api.protocol)||api.username||api.password||api.search||api.hash)throw new Error('apiBase must be an HTTP(S) origin without credentials.');
if(!/^\d+\.\d+\.\d+$/.test(config.version))throw new Error('version must be x.y.z');
if(config.wechatAppId&&!/^wx[a-z0-9]{16}$/i.test(config.wechatAppId))throw new Error('Invalid WeChat AppID.');
if(!/^\/[a-zA-Z0-9_\-/]*\/$/.test(config.webBase))throw new Error('webBase must begin and end with /.');
const manifest=read('src/manifest.json');
manifest.name=config.name;manifest.description=config.description;manifest.versionName=config.version;
manifest.versionCode=String(config.version.split('.').reduce((a,n)=>a*100+Number(n),0));
manifest.appid=config.dcloudAppId||'';manifest['mp-weixin'].appid=config.wechatAppId||'';
manifest.h5.title=config.name;manifest.h5.router.base=config.webBase;
fs.writeFileSync(path.join(root,'src/manifest.json'),JSON.stringify(manifest,null,2)+'\n');
fs.writeFileSync(path.join(root,'src/config.generated.js'),'// Generated from config/project.json. Author: UniVerse Team.\nexport default '+JSON.stringify({apiBase:api.origin,version:config.version,name:config.name})+';\n');
const python=process.env.UNIVERSE_PYTHON||path.join(backend,'.venv','Scripts','python.exe');
if(fs.existsSync(python)&&fs.existsSync(path.join(backend,'campus','ui_language.py'))){
 const result=spawnSync(python,[path.join(root,'scripts/sync-locales.py'),backend],{cwd:root,stdio:'inherit',env:{...process.env,PYTHONUTF8:'1'}});
 if(result.status!==0)throw new Error('Language catalog export failed.');
}else console.log('Using the checked-in language catalog. Configure backendPath to sync with the server.');
const cli=path.join(root,'node_modules/@dcloudio/vite-plugin-uni/bin/uni.js');
if(!fs.existsSync(cli))throw new Error('Install dependencies first: run 01-安装依赖.cmd');
const built=[];
for(const mode of chosen==='all'?Object.keys(modes):[chosen]){
 console.log('\nBuilding '+mode+' …');
 const result=spawnSync(process.execPath,[cli,'build',...modes[mode]],{cwd:root,stdio:'inherit'});
 if(result.status!==0)process.exit(result.status||1);
 if(mode==='app'){const file=path.join(root,'dist/build/app/manifest.json');const m=JSON.parse(fs.readFileSync(file,'utf8'));m.developer={...m.developer,name:config.author};fs.writeFileSync(file,JSON.stringify(m,null,2)+'\n')}
 built.push(mode);
}
if(process.argv.includes('--deploy')){
 if(!built.includes('web'))throw new Error('Build web before deploying.');
 if(!fs.existsSync(path.join(backend,'manage.py'))||!fs.existsSync(path.join(backend,'mobile_api/views.py')))throw new Error('backendPath must point to the integrated UniVerse Django project.');
 const source=path.join(root,'dist/build/h5'),target=path.join(backend,'static/mobile');
 if(!fs.existsSync(path.join(source,'index.html')))throw new Error('Missing web build.');
 fs.mkdirSync(target,{recursive:true});
 function copy(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
  if(entry.isSymbolicLink())throw new Error('Unexpected symlink in build output.');
  const from=path.join(dir,entry.name),to=path.resolve(target,path.relative(source,from));
  if(!to.startsWith(path.resolve(target)+path.sep))throw new Error('Output path escaped target.');
  if(entry.isDirectory()){fs.mkdirSync(to,{recursive:true});copy(from)}else fs.copyFileSync(from,to);
 }}
 copy(source);console.log('Web updated: '+target+' → '+config.webBase);
}
let androidApkGenerated=false;
const apkBuilder=path.join(root,'android/build_apk.py');
if(built.includes('app')&&config.androidServerOrigin&&fs.existsSync(apkBuilder)){
 console.log('\nBuilding the installable Android website test client …');
 const result=spawnSync(python,[apkBuilder,'--config',path.join(root,'config/project.json')],{cwd:root,stdio:'inherit',env:{...process.env,PYTHONUTF8:'1'}});
 if(result.status!==0)throw new Error('Android APK build failed.');
 androidApkGenerated=true;
}
const result={author:config.author,version:config.version,builtAt:new Date().toISOString(),targets:built,webDeployed:process.argv.includes('--deploy'),wechatAppIdConfigured:!!config.wechatAppId,dcloudAppIdConfigured:!!config.dcloudAppId,appOutput:'dist/build/app contains uni-app resources; android/ builds the separate Android WebView test APK.',androidApkGenerated};
fs.mkdirSync(path.join(root,'docs'),{recursive:true});fs.writeFileSync(path.join(root,'docs/build-result.json'),JSON.stringify(result,null,2)+'\n');
console.log('\nDone. Web / dist/build/h5; WeChat / dist/build/mp-weixin; App resources / dist/build/app.');
