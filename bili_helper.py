"""
Bilibili MCP Client helper for LearnForge / Antigravity
Wraps npx -y @xzxzzx/bilibili-mcp@latest to provide direct transcript, metadata, and search functions.
"""
import subprocess
import json
import sys
import io

class BilibiliClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            ['npx', '-y', '@xzxzzx/bilibili-mcp@latest'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        # Initialize MCP handshake
        init_req = {
            'jsonrpc': '2.0',
            'id': 0,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'learnforge-client', 'version': '1.0'}
            }
        }
        self._send(init_req)
        self._recv()

    def _send(self, obj):
        line = json.dumps(obj, ensure_ascii=False) + '\n'
        self.proc.stdin.write(line.encode('utf-8'))
        self.proc.stdin.flush()

    def _recv(self):
        line = self.proc.stdout.readline()
        if not line:
            return None
        return json.loads(line.decode('utf-8'))

    def call_tool(self, name, args):
        req = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': name,
                'arguments': args
            }
        }
        self._send(req)
        resp = self._recv()
        if not resp or 'result' not in resp:
            return {'error': resp}
        content = resp['result'].get('content', [])
        if content and content[0].get('type') == 'text':
            try:
                return json.loads(content[0]['text'])
            except Exception:
                return {'raw': content[0]['text']}
        return resp['result']

    def get_transcript(self, bvid_or_url):
        return self.call_tool('get_video_transcript', {'bvid_or_url': bvid_or_url})

    def get_metadata(self, bvid_or_url):
        return self.call_tool('get_video_metadata', {'bvid_or_url': bvid_or_url})

    def search_videos(self, query, page=1):
        return self.call_tool('search_bilibili_videos', {'query': query, 'page': page})

    def search_creators(self, query):
        return self.call_tool('search_bilibili_creators', {'query': query})

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass

if __name__ == '__main__':
    client = BilibiliClient()
    print('Testing search_videos...')
    res = client.search_videos('可厉害的土豆 密码学')
    print('Search res count:', len(res.get('results', [])))
    for v in res.get('results', []):
        print(f"[{v.get('bvid')}] {v.get('title')}")
    client.close()
