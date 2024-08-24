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
logger = getLogger(__name__)


def worker_job(sname, version, script):
    rla = read_rla(BytesIO(script), version)
    dump(rla, open(sname + '.json', 'w'), indent=4, ensure_ascii=False)

def main_rla2json(args):
    with open(args.infile,'rb') as f:
        env = load_assetbundle(f)
        datas = dict()
        for obj in env.objects:
            if obj.type in {ClassIDType.TextAsset}:
                data = obj.read()
                datas[data.name] = data 
        header = datas.get('sekai.rlh', None)
        assert header, "RLH Header file not found!"
        makedirs(args.outdir, exist_ok=True)
        header = loads(header.text)
        dump(header, open(path.join(args.outdir, 'sekai.rlh.json'), 'w'), indent=4, ensure_ascii=False)
        version = tuple(map(int, header['version'].split('.')))
        splitSeconds = header['splitSeconds']
        logger.info('Version: %d.%d' % version)
        logger.info('Count: %d' % len(header['splitFileIds']))        
        with ProcessPoolExecutor() as executor:
            logger.info('Dumping RLA data with %d processors' % executor._max_workers)
            futures = []
            for sid in header['splitFileIds']:
                sname = 'sekai_%2d_%08d' % (splitSeconds, sid)
                script = datas[sname + '.rla'].script.tobytes()                
                futures.append(executor.submit(worker_job, path.join(args.outdir,sname), version, script))
            finsihed_futures = set()
            with tqdm(total=len(futures)) as pbar:
                while len(finsihed_futures) < len(futures):
                    for i, future in enumerate(futures):
                        if future.done() and i not in finsihed_futures:
                            pbar.update(1)
                            finsihed_futures.add(i)
                    sleep(.1)