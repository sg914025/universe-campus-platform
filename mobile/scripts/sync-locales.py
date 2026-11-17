# Author: UniVerse Team. Export existing interface copy without patient or user content.
import importlib.util,json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
config=json.loads((root/'config/project.json').read_text(encoding='utf-8-sig'))
backend=Path(sys.argv[1] if len(sys.argv)>1 else config['backendPath'])
spec=importlib.util.spec_from_file_location('campus_copy',backend/'campus/ui_language.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
keys=set()
for p in (root/'src').rglob('*'):
 if p.suffix in ('.vue','.js'):
  keys.update(re.findall(r"['\"]([^'\"\n]*[\u4e00-\u9fff][^'\"\n]*)['\"]",p.read_text(encoding='utf-8-sig')))
keys={k for k in keys if '<' not in k and '>' not in k}
# Include server-defined service labels in the same exported catalog.
keys.update(['A 楼','B 楼','C 楼','图书馆','其他楼栋','自习室','篮球场','羽毛球场','乒乓球台','足球场'])
catalog={k:v for k,v in module.TRANSLATIONS.items() if k in keys}
extra=root/'config/client-locales.json'
if extra.exists():
 for key,value in json.loads(extra.read_text(encoding='utf-8-sig')).items():catalog.setdefault(key,{}).update(value)
(root/'src/lib/locales.generated.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
missing={lang:sorted(k for k in keys if not catalog.get(k,{}).get(lang)) for lang in ['en','ru','ja']}
(root/'docs/translation-gaps.json').write_text(json.dumps(missing,ensure_ascii=False,indent=2),encoding='utf-8')
print('Exported',len(catalog),'labels; gaps', {k:len(v) for k,v in missing.items()})
