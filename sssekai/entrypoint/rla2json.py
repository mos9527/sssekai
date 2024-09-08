from os import path,makedirs
from json import loads,dump
from io import BytesIO
from logging import getLogger
from concurrent.futures import ProcessPoolExecutor
from time import sleep
from sssekai.unity.AssetBundle import load_assetbundle
from UnityPy.enums import ClassIDType
from sssekai.fmt.rla import read_rla
from tqdm import tqdm
import zipfile, base64
logger = getLogger(__name__)

def dump_json_job(sname, version, script):
    rla = read_rla(BytesIO(script), version)
    dump(rla, open(sname + '.json', 'w', encoding='utf-8'), indent=4, ensure_ascii=False)

def dump_audio_job(sname, version, script):
    rla = read_rla(BytesIO(script), version)
    for tick, data in rla.items():
        data = data.get('SoundData', None)
        if data:
            for i, b64data in enumerate(data):
                fname = sname + '_%d_%d.hca' % (i, tick)
                raw_data = base64.b64decode(b64data['data'])
                with open(fname, 'wb') as f: f.write(raw_data)

def main_rla2json(args):
    with open(args.infile,'rb') as f:        
        datas = dict()
        if f.read(2) == b'PK':
            f.seek(0)            
            with zipfile.ZipFile(f, 'r') as z:
                for name in z.namelist():
                    with z.open(name) as zf:
                        datas[name] = zf.read()
        else:
            f.seek(0)
            rla_env = load_assetbundle(f)            
            for obj in rla_env.objects:
                if obj.type in {ClassIDType.TextAsset}:
                    data = obj.read()
                    datas[data.name] = data.script.tobytes()
        header = datas.get('sekai.rlh', None)
        assert header, "RLH Header file not found!"
        makedirs(args.outdir, exist_ok=True)
        header = loads(header.decode('utf-8'))
        splitSeconds = header['splitSeconds']

        dump(header, open(path.join(args.outdir, 'sekai.rlh.json'), 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
        version = tuple(map(int, header['version'].split('.')))
        logger.info('Version: %d.%d' % version)
        logger.info('Count: %d' % len(header['splitFileIds']))        

        worker_job = dump_json_job
        if args.dump_audio:
            worker_job = dump_audio_job
            logger.info('Dumping RLA raw HCA audio data')
        else:
            logger.info('Dumping RLA data to JSON')
        with ProcessPoolExecutor() as executor:
            if not args.no_parallel:
                logger.info('Dumping RLA data with %d processors' % executor._max_workers)
            futures = []
            for sid in header['splitFileIds']:
                sname = 'sekai_%2d_%08d' % (splitSeconds, sid)
                script = datas[sname + '.rla']
                if args.no_parallel:
                    worker_job(path.join(args.outdir,sname), version, script)
                else:
                    futures.append(executor.submit(worker_job, path.join(args.outdir,sname), version, script))
            finsihed_futures = set()
            with tqdm(total=len(futures)) as pbar:
                while len(finsihed_futures) < len(futures):
                    for i, future in enumerate(futures):
                        if future.done() and i not in finsihed_futures:
                            pbar.update(1)
                            finsihed_futures.add(i)
                    sleep(.1)