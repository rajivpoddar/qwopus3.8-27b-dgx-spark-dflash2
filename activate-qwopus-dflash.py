"""Clone the live Qwopus profile, adding only the preserved Pango draft flags.

Default: read-only preflight. --activate requires paused clients and fenced MoP.
Rollback: docker stop qwopus-pango-dflash; docker start qwopus-pango.
"""
import copy
import http.client
import json
import socket
import subprocess
import sys
from pathlib import Path

SOURCE = 'qwopus-pango'
TARGET = 'qwopus-pango-dflash'
IMAGE = 'sha256:db815495d86fa23ffa3c898ca48d3dcb5e2a09240a092fd99e4601bd53274bfa'
DRAFT_REVISION = 'bd7a934213c47a9e7ef69eef36bb3325f47fd1f1'

def run(*args):
    return subprocess.check_output(args, text=True).strip()

class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect('/var/run/docker.sock')

def main():
    source = json.loads(run('docker', 'inspect', SOURCE))[0]
    old = json.loads(run('docker', 'inspect', 'qwen38-pango'))[0]
    assert source['Image'] == old['Image'] == IMAGE
    assert source['State']['Running'] and not old['State']['Running']
    assert TARGET not in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines()
    config = copy.deepcopy(source['Config'])
    assert not any(x.startswith('--speculative-') for x in config['Cmd'])
    args = old['Config']['Cmd']
    flags = {x: args[i+1] for i, x in enumerate(args) if x.startswith('--speculative-')}
    assert flags['--speculative-algorithm'] == 'DFLASH'
    assert flags['--speculative-draft-model-revision'] == DRAFT_REVISION
    p = Path('/home/user/.cache/huggingface/hub/models--maurienne-ai--Qwen3.8-27B-DFlash2-NVFP4-RTNcal/snapshots') / DRAFT_REVISION
    assert (p/'model.safetensors').is_file()
    assert json.loads((p/'config.json').read_text())['architectures'] == ['DFlash2DraftModel']
    for k, v in flags.items():
        config['Cmd'].extend([k, v])
    config['Image'] = IMAGE
    config['HostConfig'] = copy.deepcopy(source['HostConfig'])
    if '--activate' not in sys.argv:
        print(json.dumps({'state':'PREFLIGHT_OK','source':SOURCE,'target':TARGET,'draft':flags}))
        return
    conn = DockerConnection('localhost')
    conn.request('POST', '/containers/create?name='+TARGET, json.dumps(config), {'Content-Type':'application/json'})
    response = conn.getresponse()
    response.read()
    assert response.status == 201, 'candidate creation failed; source unchanged'
    try:
        run('docker','stop','-t','30',SOURCE)
        run('docker','start',TARGET)
    except Exception:
        subprocess.run(['docker','stop','-t','10',TARGET],capture_output=True)
        run('docker','start',SOURCE)
        raise
    print(json.dumps({'state':'STARTING_NOT_READY','source_preserved':SOURCE,'target':TARGET}))

if __name__ == '__main__':
    main()
