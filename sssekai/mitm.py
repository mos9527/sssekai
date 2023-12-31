import json
from mitmproxy import http
from crypto import sekai_api_encrypt, sekai_api_decrypt
from msgpack import unpackb, packb
import datetime, copy

class APIIntereceptor:
    @staticmethod
    def file_id(flow: http.HTTPFlow):
        return '%s_%s' % (datetime.datetime.now().strftime("%H_%M_%S") , flow.request.path.split('/')[-1].split('.')[0].split('?')[0])
        
    @staticmethod
    def filter(flow: http.HTTPFlow):
        TW_HOSTS = {
            'mk-zian-obt-cdn.bytedgame.com',
            'mk-zian-obt-https.bytedgame.com'
        }
        return flow.request.host_header in TW_HOSTS

    @staticmethod
    def log_flow(data : bytes, flow: http.HTTPFlow) -> dict | None:
        if (len(data)):
            prefix = 'request'
            if (flow.response):
                prefix = 'response'
            try:
                print(">>> %s <<<" % prefix.upper())
                decrypted_body = sekai_api_decrypt(data)
                body = unpackb(decrypted_body)
                print("::",flow.request.url)
                with open('logs/%s_%s.json' % (prefix,APIIntereceptor.file_id(flow)),'w',encoding='utf-8') as f:
                    f.write(json.dumps(body,indent=4,ensure_ascii=False))
                return body
            except Exception as e:
                print(">>> ERROR <<<")
                print(e)
                print(flow.request.url)
                with open('logs_bin/%s_%s.bin' % (prefix,APIIntereceptor.file_id(flow)),'wb') as f:
                    if (flow.response):
                        f.write(flow.response.content)
                    else:
                        f.write(flow.request.content)
    
    def request(self,flow: http.HTTPFlow):
        print(flow.request.host_header)
        if self.filter(flow):
            body = self.log_flow(flow.request.content, flow)
            if body:
                if 'musicDifficultyId' in body:
                    print('! Intercepted Live request')
                    body['musicId'] = 1 # Tell Your World
                    body['musicDifficultyId'] = 4 # Expert
                flow.request.content = sekai_api_encrypt(packb(body))

    def response(self, flow : http.HTTPFlow):
        if self.filter(flow):
            body = self.log_flow(flow.response.content, flow)
            if body:
                if 'userMusics' in body:
                    print('! Intercepted userMusics')
                    existing = {music['musicId'] : music for music in body['userMusics']}
                    body['userMusics'] = []
                    for i in range(1, 1000):
                        if i in existing:
                            body['userMusics'].append(existing[i])
                        else:
                            print('Appended %d' % i)
                            new_song = copy.deepcopy(existing[1])
                            new_song['musicId'] = i
                        
                        for stat in body['userMusics'][-1]['userMusicDifficultyStatuses']:
                            stat['musicDifficultyStatus'] = 'available'
                    flow.response.content = sekai_api_encrypt(packb(body))            

addons = [
    APIIntereceptor()
]