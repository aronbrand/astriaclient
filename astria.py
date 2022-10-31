from pathlib import Path
import requests
import argparse
import random
import json
import os
import sys
import time
import logging
import shelve

from urllib.parse import urlparse
import http.client as http_client

# Client SDK for Astria API
class Astria():
    def __init__(self, apikey):
        self.apikey = apikey

    def post(self, url, formargs):
        return requests.post(url, data=formargs, headers={"Authorization":"Bearer "+self.apikey})

    def get(self, url):
        return requests.get(url, headers={"Authorization":"Bearer "+self.apikey})

    def gen(self, tuneid, prompt, steps=50, seed=100, callback=''):
        formargs = { 
            'prompt[text]' : prompt, 
            'prompt[steps]' : steps,
            'prompt[seed]' : seed,
            'prompt[callback]' : callback 
            }
        return self.post('https://api.astria.ai/tunes/' + str(tuneid) + '/prompts', formargs)

    def tune(self, title, name, images, callback='', branch='fast'):
        if len(images) < 10:
            raise Exception("At least 10 images should be provided")

        formargs = { 
            'tune[title]' : title, 
            'tune[branch]' : branch,
#            'tune[callback]' : callback,
            'tune[name]' : name
            }

        myfiles = []

        for f in images:
            myfiles.append(('tune[images][]', open(f ,'rb')))

        return requests.post('https://api.astria.ai/tunes', data=formargs, headers={"Authorization":"Bearer "+self.apikey}, files=myfiles)

    def list(self, tuneid, offset=0):
        return self.get('https://api.astria.ai/tunes/' + str(tuneid) + '/prompts?offset='  + str(offset))

    def promptinfo(self, tuneid, promptid):
        return self.get('https://api.astria.ai/tunes/' + str(tuneid) + '/prompts/'  + str(promptid))

    def waitfor(self, tuneid, promptid):

        while True:
            info = self.promptinfo (tuneid, promptid).json()
            self.reportprogress()
            if (info['images']):
                break
            time.sleep(2.5)
            
        self.reportprogress(done = True)
        return 0

    def reportprogress (self, done = False):
        print('.', end='', flush=True)
        if (done):
            print ()

    def download(self, tuneid, promptid, wait=False):
        if (wait):
            self.waitfor(tuneid, promptid)

        promptinfo = self.promptinfo(tuneid, promptid).json()

        i = 0
        for url in promptinfo['images']:
            outfile = Path(str(tuneid) + '_' + str(promptinfo['id']) + '_' + str(promptinfo['seed']) + '_' + str(i) + '.jpg')
            if outfile.exists():
                logging.info(str(outfile) + " already exists - skipping")
                continue

            response = requests.get (url)
            outf = open (outfile, "wb")
            outf.write(response.content)
            outf.close()
            logging.info (str(outfile) + " DONE\n")
            i = i + 1

    def downloadAll(self, tuneid, limit, dbfile):
        results = 0
        assert (limit > 0)

        with shelve.open(dbfile, flag='c') as db:
            while (1):
                lastprompts = self.list(tuneid, results).json()

                if not lastprompts:
                    return

                for prompt in lastprompts:
                    id = prompt['id']
                    if str(id) in db:
                        logging.info("prompt " + str(id) +  " already downloaded - skipping")
                    elif prompt['images']:
                        self.download(tuneid, id)
                        db[str(id)] = prompt
                    results = results + 1
                    if (results > limit):
                        return



####################################
# Command line interface
def do_gen(args):
    astria = Astria(args.key)
    results = []

    for prompt in args.prompts:
        print ('GENERATING  ' + prompt + ':\n')
        result = astria.gen(args.tuneid, prompt, args.steps, args.seed, args.callback).json()     
        print (json.dumps(result, indent=4))
        results.append(result)
    if (args.download):
        for r in results:
            print ('DOWNLOADING  ' + str(r['id']) + ':'+ str(r['text']) + '\n')
            astria.download(args.tuneid, r['id'], wait=True)

def do_tune(args):
    astria = Astria(args.key)
    
    branch = 'fast' if args.test else ''
  
    result = astria.tune(args.title, args.name, args.images, args.callback, branch)
    print (json.dumps(result.json(), indent=4))

def do_list(args):
    astria = Astria(args.key)
    result = astria.list(args.tuneid)
    print (json.dumps(result.json(), indent=4))

def do_promptinfo(args):
    astria = Astria(args.key)
    result = astria.promptinfo(args.tuneid, args.promptid)
    print (json.dumps(result.json(), indent=4))

def do_download(args):
    astria = Astria(args.key)
    astria.download(args.tuneid, args.promptid, args.wait)

def do_download_all(args):
    astria = Astria(args.key)
    astria.downloadAll(args.tuneid, args.limit, args.db)

def environ_or_required(key):
    return (
        {'default': os.environ.get(key)} if os.environ.get(key)
        else {'required': True}
    )

def main() -> int:
    parser = argparse.ArgumentParser(description='Command line tool for Astria',fromfile_prefix_chars='@')
    parser.add_argument('--key', type=str, help='Astria API token', **environ_or_required('ASTRIA_API_TOKEN') )
    parser.add_argument('--callback', type=str, default='')
    parser.add_argument('--debug', action='store_true')

    subparsers = parser.add_subparsers()

    parser_gen = subparsers.add_parser('gen', help='Generate images for prompts')
    parser_gen.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_gen.add_argument('prompts', nargs='+',type=str, help='Prompts to generate')
    parser_gen.add_argument('--seed', type=int, default=random.randrange(1,9999))
    parser_gen.add_argument('--steps', type=int, default=50)
    parser_gen.add_argument('--download', action='store_true', help='Download results')
    parser_gen.set_defaults(func=do_gen)

    parser_tune = subparsers.add_parser('tune', help='Create a new tune')
    parser_tune.add_argument('title', type=str, help='Descriptive name for this tuning')
    parser_tune.add_argument('name', type=str, help='Dreambooth classname (style, person, man, woman etc)')
    parser_tune.add_argument('images', nargs='+', type=str, help='At least 10 image filenames')
    parser_tune.add_argument('--test', action='store_true', help='Use fast testing branch')
    parser_tune.set_defaults(func=do_tune)

    parser_list = subparsers.add_parser('list', help='List generated images')
    parser_list.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_list.set_defaults(func=do_list)

    parser_details = subparsers.add_parser('info', help='Get details of prompt')
    parser_details.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_details.add_argument('promptid', type=int, help='Prompt ID')
    parser_details.set_defaults(func=do_promptinfo)

    parser_download = subparsers.add_parser('download', help='Download images of prompt')
    parser_download.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_download.add_argument('promptid', type=int, help='Prompt ID')
    parser_download.add_argument('--wait', action='store_true', help='Wait for results to be ready')
    parser_download.set_defaults(func=do_download)

    parser_downloadall = subparsers.add_parser('downloadall', help='Download recent images')
    parser_downloadall.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_downloadall.add_argument('--limit', type=int, help='Maximum number of prompts to download', default=10)
    parser_downloadall.add_argument('--db', type=str, help='Keep list of previously downloaded prompts in a DB file', default="astriacache")
    parser_downloadall.set_defaults(func=do_download_all)

    args=parser.parse_args()

    logging.getLogger('root').setLevel(logging.INFO)
    if (args.debug):
        http_client.HTTPConnection.debuglevel = 1
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    args.func(args)
    return 0

if __name__ == '__main__':
    sys.exit(main())  