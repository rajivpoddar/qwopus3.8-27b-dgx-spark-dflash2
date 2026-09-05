"""Server-only trial from the exact deployed Pango config; slots are managed separately.

Default is read-only preflight. Run --activate only after pausing clients and MoP.
Rollback: docker stop qwopus-pango; docker start qwen38-pango.
"""
import copy
import http.client
import json
from pathlib import Path
import socket
import subprocess
import sys

SOURCE = 'qwen38-pango'
TARGET = 'qwopus-pango'
IMAGE = 'sha256:db815495d86fa23ffa3c898ca48d3dcb5e2a09240a092fd99e4601bd53274bfa'
MODEL_DIR = '/home/user/models/qwopus-nvfp4-e1fad175'
REVISION = 'e1fad175b1f069b9e19a0293c561cefb516df7e4'

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def candidate(original):
    assert original['Image'] == IMAGE
    config = copy.deepcopy(original['Config'])
    args = config['Cmd']
    replacement = {'--model-path':'/model', '--tool-call-parser':'qwen',
                   '--mamba-full-memory-ratio':'0.9',
                   '--chat-template':'/model/chat_template.jinja',
                   '--default-chat-template-kwargs':'{"enable_thinking":true,"preserve_thinking":false}'}
    out = []
    i = 0
    while i < len(args):
        flag = args[i]
        if flag.startswith('--speculative-') or flag == '--revision':
            i += 2
        elif flag in replacement:
            out.extend([flag, replacement.pop(flag)])
            i += 2
        else:
            out.append(flag)
            i += 1
    assert not replacement
    config['Cmd'] = out
    config['Image'] = IMAGE
    config['HostConfig'] = copy.deepcopy(original['HostConfig'])
    config['HostConfig']['Binds'].append(MODEL_DIR + ':/model:ro')
    return config

class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect('/var/run/docker.sock')

def main():
    original = json.loads(run('docker', 'inspect', SOURCE))[0]
    reconfigure = '--reconfigure' in sys.argv
    if reconfigure:
        assert not original['State']['Running']
        assert TARGET + '-initial-cache' not in run('docker','ps','-a','--format','{{.Names}}').splitlines()
    else:
        assert TARGET not in run('docker','ps','-a','--format','{{.Names}}').splitlines()
    p = Path(MODEL_DIR)
    assert (p/'.cache/huggingface/download/config.json.metadata').read_text().splitlines()[0] == REVISION
    index = json.loads((p/'model.safetensors.index.json').read_text())
    assert all((p/n).is_file() for n in set(index['weight_map'].values()))
    config = candidate(original)
    if '--activate' not in sys.argv:
        print(json.dumps({'state':'PREFLIGHT_OK','source':SOURCE,'target':TARGET,'image':IMAGE,'revision':REVISION,'speculation':False,'thinking_default':True}))
        return
    assert original['State']['Running'] or reconfigure
    if reconfigure:
        run('docker','stop','-t','15',TARGET)
        run('docker','rename',TARGET,TARGET+'-initial-cache')
    conn = DockerConnection('localhost')
    # Create stopped candidate first: failure here leaves the source untouched.
    conn.request('POST','/containers/create?name='+TARGET,json.dumps(config),{'Content-Type':'application/json'})
    response = conn.getresponse()
    response.read()
    assert response.status == 201, 'candidate creation failed'
    try:
        run('docker','stop','-t','30',SOURCE)
        run('docker','start',TARGET)
    except Exception:
        subprocess.run(['docker','stop','-t','10',TARGET],capture_output=True)
        run('docker','start',SOURCE)
        raise
    print(json.dumps({'state':'STARTING_NOT_READY','source_preserved':SOURCE,'target':TARGET,'revision':REVISION}))

if __name__ == '__main__':
    main()
