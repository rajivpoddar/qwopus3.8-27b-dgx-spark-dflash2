"""Deploy cached effort image only after pausing clients and fencing MoP."""
import copy
import http.client
import json
import socket
import subprocess

SOURCE = 'qwopus-pango-dflash-compaction'
TARGET = 'qwopus-pango-dflash-effort'
IMAGE = 'sha256:e11dc62385a2af8c0a242a5eb85490b91844d897605166b26c72e645b408f121'

def run(*args):
    return subprocess.check_output(args, text=True).strip()

class Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect('/var/run/docker.sock')

source = json.loads(run('docker', 'inspect', SOURCE))[0]
assert source['State']['Running']
assert source['Image'] == 'sha256:dedc2d97b119189879fc4dbcd3618b047be0eb3a011adc81530b886a2fb7bffc'
assert run('docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE) == IMAGE
assert TARGET not in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines()
config = copy.deepcopy(source['Config'])
config['Image'] = IMAGE
cmd = config['Cmd']
if '--grammar-backend' in cmd:
    i = cmd.index('--grammar-backend')
    del cmd[i:i+2]
if '--enable-strict-thinking' not in cmd:
    cmd.append('--enable-strict-thinking')
cmd.extend(['--grammar-backend', 'xgrammar'])
config['Env'] = [e for e in config['Env'] if e.split('=', 1)[0] not in ('QWOPUS_EFFORT_BUDGETS', 'SGLANG_MAX_THINK_TOKENS')]
config['Env'].extend(['QWOPUS_EFFORT_BUDGETS=1', 'SGLANG_MAX_THINK_TOKENS=1024'])
config['HostConfig'] = copy.deepcopy(source['HostConfig'])
conn = Connection('localhost')
conn.request('POST', '/containers/create?name=' + TARGET, json.dumps(config), {'Content-Type': 'application/json'})
response = conn.getresponse()
response.read()
assert response.status == 201
try:
    run('docker', 'stop', '-t', '30', SOURCE)
    run('docker', 'start', TARGET)
except Exception:
    subprocess.run(['docker', 'stop', '-t', '10', TARGET], capture_output=True)
    run('docker', 'start', SOURCE)
    raise
print('STARTING_NOT_READY; rollback source preserved: ' + SOURCE)
