"""Image-only deployment. Requires paused clients and MoP maintenance fence."""
import copy
import http.client
import json
import socket
import subprocess

SOURCE = 'qwopus-pango-dflash'
TARGET = 'qwopus-pango-dflash-compaction'
IMAGE = 'sha256:dedc2d97b119189879fc4dbcd3618b047be0eb3a011adc81530b886a2fb7bffc'

def run(*args):
    return subprocess.check_output(args, text=True).strip()

class Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect('/var/run/docker.sock')

source = json.loads(run('docker', 'inspect', SOURCE))[0]
assert source['State']['Running']
assert source['Image'] == 'sha256:db815495d86fa23ffa3c898ca48d3dcb5e2a09240a092fd99e4601bd53274bfa'
assert run('docker', 'image', 'inspect', '--format', '{{.Id}}', IMAGE) == IMAGE
assert TARGET not in run('docker', 'ps', '-a', '--format', '{{.Names}}').splitlines()
config = copy.deepcopy(source['Config'])
config['Image'] = IMAGE
config['HostConfig'] = copy.deepcopy(source['HostConfig'])
conn = Connection('localhost')
conn.request('POST', '/containers/create?name=' + TARGET, json.dumps(config), {'Content-Type':'application/json'})
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
print('STARTING_NOT_READY; source preserved: ' + SOURCE)
