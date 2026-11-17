"""Build a signed Android test APK using official Android tools. Author: UniVerse Team."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
local_sdk=root.parent/'.tools/android-sdk'
parser.add_argument('--toolchain',type=Path,default=Path(os.environ.get('UNIVERSE_ANDROID_SDK',str(local_sdk))))
parser.add_argument('--java-home',type=Path,default=Path(os.environ.get('JAVA_HOME','')))
parser.add_argument('--config',type=Path,default=root.parent/'config/project.json')
parser.add_argument('--out',type=Path,default=root.parent/'安卓安装包')
args=parser.parse_args()
config=json.loads(args.config.read_text(encoding='utf-8-sig'))
origin=config.get('androidServerOrigin')
if not origin:raise SystemExit('Configure androidServerOrigin in config/project.json first.')
java=args.java_home/'bin/java.exe';javac=args.java_home/'bin/javac.exe';keytool=args.java_home/'bin/keytool.exe'
sdk=args.toolchain
android_jar=next(sdk.glob('android-35/android.jar'))
tools=next(p.parent for p in sdk.rglob('aapt.exe'))
for file in [java,javac,keytool,android_jar,tools/'aapt.exe',tools/'zipalign.exe',tools/'lib/d8.jar',tools/'lib/apksigner.jar']:
    if not file.is_file():raise SystemExit('Missing tool: '+str(file))
args.out.mkdir(parents=True,exist_ok=True)

def run(command,**kwargs):
    if Path(command[0]).name=='java.exe':
        command=[command[0],'-Dstdout.encoding=UTF-8','-Dstderr.encoding=UTF-8','--enable-native-access=ALL-UNNAMED',*command[1:]]
    result=subprocess.run([str(p) for p in command],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace',**kwargs)
    if result.returncode:
        print(result.stdout)
        raise SystemExit('Android build command failed: '+str(command[0]))
    return result.stdout

# Legacy aapt cannot read Chinese Windows paths. Keep only its temporary build files under an ASCII path.
scratch_parent=Path(os.environ.get('UNIVERSE_ANDROID_BUILD_TEMP',str(Path(tempfile.gettempdir())/'universe-android-build')))
scratch_parent.mkdir(parents=True,exist_ok=True)
scratch=Path(tempfile.mkdtemp(prefix='universe-apk-',dir=scratch_parent))
manifest=root/'AndroidManifest.xml'
android_ns='http://schemas.android.com/apk/res/android'
ET.register_namespace('android',android_ns)
manifest_tree=ET.parse(manifest)
version=config['version']
numbers=[int(n) for n in version.split('.')]
assert len(numbers)==3 and all(0<=n<100 for n in numbers)
manifest_tree.getroot().set('{'+android_ns+'}versionName',version)
manifest_tree.getroot().set('{'+android_ns+'}versionCode',str(numbers[0]*10000+numbers[1]*100+numbers[2]))
manifest_tree.write(scratch/'AndroidManifest.xml',encoding='utf-8',xml_declaration=True)
shutil.copy2(android_jar,scratch/'android.jar')
classes=scratch/'classes';classes.mkdir()
generated=scratch/'generated';generated.mkdir()
res=scratch/'res';shutil.copytree(root/'res',res)
icon_root=args.config.parent.parent/'src/static/brand'
for density,size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
    target=res/('mipmap-'+density);target.mkdir()
    shutil.copy2(icon_root/f'icon-{size}.png',target/'ic_launcher.png')
generated_config=generated/'BuildConfig.java'
generated_config.write_text('package cn.universe.campus.preview;\npublic final class BuildConfig {\n public static final String DEFAULT_ORIGIN='+json.dumps(origin)+';\n public static final String ACCESS_ORIGIN='+json.dumps(config.get('androidAccessOrigin',''))+';\n public static final String VERSION_NAME='+json.dumps(version)+';\n}\n',encoding='utf-8')
sources=list((root/'src').rglob('*.java'))+[generated_config]
print('Compiling Android activity and URL validation …',flush=True)
run([javac,'--release','8','-encoding','UTF-8','-classpath',android_jar,'-d',classes,*sources])
test_sources=list((root/'tests').glob('*.java'))
run([javac,'-encoding','UTF-8','-classpath',classes,'-d',scratch/'tests',*test_sources])
test_result=''.join(run([java,'-cp',str(classes)+os.pathsep+str(scratch/'tests'),source.stem]) for source in test_sources)
print(test_result.strip(),flush=True)
class_jar=scratch/'classes.jar'
with zipfile.ZipFile(class_jar,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in classes.rglob('*.class'):archive.write(path,path.relative_to(classes).as_posix())
dex=scratch/'dex';dex.mkdir()
run([java,'-cp',tools/'lib/d8.jar','com.android.tools.r8.D8','--lib',android_jar,'--min-api','23','--output',dex,class_jar])
unsigned=scratch/'unsigned.apk'
run([tools/'aapt.exe','package','-f','-M',scratch/'AndroidManifest.xml','-S',res,'-I',scratch/'android.jar','-F',unsigned])
with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as archive:
    for path in dex.glob('*.dex'):archive.write(path,path.name)
    archive.writestr('assets/universe-build.json',json.dumps(dict(author='UniVerse Team',version=version,server=origin,client='Android WebView shared-site test client',builtAt=datetime.now(timezone.utc).isoformat()),ensure_ascii=False))
    archive.writestr('assets/NOTICE.txt','Author: UniVerse Team\nUses Android system WebView. Existing project and third-party licenses remain unchanged.\nTest build; no cloud signing or analytics SDK.\n')
aligned=scratch/'aligned.apk'
run([tools/'zipalign.exe','-f','-p','4',unsigned,aligned])
signing=root/'signing';signing.mkdir(exist_ok=True)
keystore=signing/'universe-test.jks'
if not keystore.exists():
    run([keytool,'-genkeypair','-keystore',keystore,'-storepass','android','-keypass','android','-alias','universe-test','-keyalg','RSA','-keysize','3072','-validity','3650','-dname','CN=UniVerse Team, OU=UniVerse Test, O=UniVerse, C=CN','-storetype','JKS','-noprompt'])
apk=scratch/'universe-signed.apk'
run([java,'-jar',tools/'lib/apksigner.jar','sign','--ks',keystore,'--ks-key-alias','universe-test','--ks-pass','pass:android','--key-pass','pass:android','--v1-signing-enabled','true','--v2-signing-enabled','true','--v3-signing-enabled','true','--out',apk,aligned])
verified=run([java,'-jar',tools/'lib/apksigner.jar','verify','--verbose','--print-certs',apk])
run([tools/'zipalign.exe','-c','-p','4',apk])
badging=run([tools/'aapt.exe','dump','badging',apk])
assert "package: name='cn.universe.campus.preview'" in badging
assert "launchable-activity: name='cn.universe.campus.preview.MainActivity'" in badging
assert "sdkVersion:'23'" in badging
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    for name in ['AndroidManifest.xml','classes.dex','resources.arsc','assets/universe-build.json']:assert name in archive.namelist(),name
    assert not any(x.lower().endswith(('.jks','.keystore','.sqlite3')) for x in archive.namelist())
sha=hashlib.sha256(apk.read_bytes()).hexdigest()
delivery=args.out/('寰校通UniVerse-安卓体验版-'+version+'.apk')
shutil.copy2(apk,delivery)
apk=delivery
(args.out/'APK-SHA256.txt').write_text(sha+'  '+apk.name+'\n',encoding='utf-8')
(args.out/'APK-签名与构建验证.txt').write_text('作者：UniVerse Team\n\n'+verified+'\n'+badging+'\n'+test_result,encoding='utf-8')
(args.out/'build-report.json').write_text(json.dumps(dict(author='UniVerse Team',apk=apk.name,bytes=apk.stat().st_size,sha256=sha,server=origin,version=version,minAndroid='6.0 (API 23)',targetSdk=35,nativeLibraries=False,signatureVerified=True,zipAlignmentVerified=True,realDeviceTested=False,clientMode='shared-site-webview',scratch=str(scratch)),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'apk':str(apk),'bytes':apk.stat().st_size,'sha256':sha,'verified':True},ensure_ascii=False),flush=True)
