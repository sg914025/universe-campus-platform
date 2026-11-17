"""由 start.cmd 调用，仅启动项目中的便携 Ollama，不修改全局设置。"""
import os
from pathlib import Path
import subprocess
from urllib.request import ProxyHandler, build_opener

root=Path(__file__).resolve().parent
executable=root/'runtime'/'ollama'/'ollama.exe'
if executable.is_file():
    try:
        with build_opener(ProxyHandler({})).open('http://127.0.0.1:11434/api/tags',timeout=2):
            print('Local AI is already running.')
    except OSError:
        env=dict(os.environ,OLLAMA_MODELS=str(root/'runtime'/'models'),OLLAMA_HOST='127.0.0.1:11434',OLLAMA_NO_CLOUD='1')
        with (root/'runtime'/'ollama.log').open('ab') as log:
            subprocess.Popen([str(executable),'serve'],cwd=root,env=env,stdout=log,stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        print('Local AI is starting in the background.')
else:
    print('Local AI runtime is missing. Basic follow-up questions remain available.')
