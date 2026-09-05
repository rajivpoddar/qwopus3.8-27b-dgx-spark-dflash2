"""Server-only experiment; requires paused clients and MoP fence."""
import copy
import http.client
import json
import socket
import subprocess

SOURCE = 'qwopus-pango-dflash-effort'
TARGET = 'qwopus-pango-dflash-thinking-off'
IMAGE = 'sha256:dd967e4ffa4bf055589c5a8fda4a8823b2c9f33b89dc622087d35667babb1c65'

def run(*args):
    return subprocess.check_output(args, text=True).strip()

class Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect('/var/run/docker.sock')

source = json.loads(run('docker', 'inspect', SOURCE))[0]
assert source['State']['Running']
assert source['Image'] == 'sha256:e11dc62385a2af8c0a242a5eb85490b91844d897605166b26c72e645b408f121'
assert run('docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE) == IMAGE
assert TARGET not in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines()
config = copy.deepcopy(source['Config'])
config['Image'] = IMAGE
config['Env'] = [e for e in config['Env'] if not e.startswith('QWOPUS_FORCE_THINKING_OFF=')]
config['Env'].append('QWOPUS_FORCE_THINKING_OFF=1')
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
