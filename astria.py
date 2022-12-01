#!/usr/bin/env python3
 
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

    def post(self, url : str, formargs):
        return requests.post(url, data=formargs, headers={"Authorization":"Bearer "+self.apikey})

    def get(self, url : str):
        return requests.get(url, headers={"Authorization":"Bearer "+self.apikey})

    def gen(self, tuneid, prompt : str, steps=50, seed=100, callback=''):
        """Generate images with a prompt for a given finetune ID

        Args:
            tuneid (_type_): Astria finetune ID
            prompt (str): The prompt to generate
            steps (int, optional): Number of inference steps. Defaults to 50.
            seed (int, optional): The random seed to use. Defaults to 100.
            callback (str, optional): Address of a webhook to call on completion. Defaults to ''.

        Returns:
            _type_: _description_
        """
        formargs = { 
            'prompt[text]' : prompt, 
            'prompt[steps]' : steps,
            'prompt[seed]' : seed,
            'prompt[callback]' : callback 
            }
        return self.post('https://api.astria.ai/tunes/' + str(tuneid) + '/prompts', formargs)

    def tune(self, title : str, classname : str, images, callback='', branch='fast'):
        """Train a new dreambooth model based on a set of images

        Args:
            title (str): _description_
            images (list of strings): set of filenames to use for training
            classname (str, optional): Dreambooth class name such as person, man, or woman. Defaults to 'person'.
            callback (str, optional): Webhook address. Defaults to ''.
            branch (str, optional): Astria model branch to use. Defaults to 'fast'.

        Raises:
            Exception: _description_
        """
        if len(images) < 10:
            raise Exception("At least 10 images should be provided")

        formargs = { 
            'tune[title]' : title, 
            'tune[branch]' : branch,
#            'tune[callback]' : callback,
            'tune[name]' : classname
            }

        myfiles = []

        for f in images:
            myfiles.append(('tune[images][]', open(f ,'rb')))

        return requests.post('https://api.astria.ai/tunes', data=formargs, headers={"Authorization":"Bearer "+self.apikey}, files=myfiles)

    def listtune(self):
        """List the tunes in the account
 
        Returns:
            Json : The results
        """
        return self.get('https://api.astria.ai/tunes/')
        
        
    def list(self, tuneid, offset=0):
        """List the generations for a given finetune

        Args:
            tuneid (int): The astria tune ID to list
            offset (int, optional): Offset for the listing. Defaults to 0.

        Returns:
            Json : The results
        """
        result = self.get('https://api.astria.ai/tunes/' + str(tuneid) + '/prompts?offset='  + str(offset)).json()

        if ('error' in result):
            raise Exception(result['error'])

        return result

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

    def downloadPromptImages(self, tuneid, promptid, wait=False, targetdir='.'):
        """Download all the images of a specified prompt

        Args:
            tuneid (int): ID of the astria tune
            promptid (int): ID of the prompt to download
            wait (bool, optional): Block until results are ready. Defaults to False.
        """
        if (wait):
            self.waitfor(tuneid, promptid)

        promptinfo = self.promptinfo(tuneid, promptid).json()

        if not Path(targetdir).exists():
            os.mkdir(targetdir)

        i = 0
        for url in promptinfo['images']:
            outfile = Path(targetdir, str(tuneid) + '_' + str(promptinfo['id']) + '_' + str(promptinfo['seed']) + '_' + str(i) + '.jpg')
            if outfile.exists():
                logging.info(str(outfile) + " already exists - skipping")
                continue

            try:
                response = requests.get (url)

                with open (outfile, "wb") as outf:
                    outf.write(response.content)

                logging.info (str(outfile) + " DONE")
            except requests.exceptions.RequestException as e:
                logging.error (str(outfile) + " Request failed: " +  repr(e))

            i = i + 1

    def downloadTuneImages(self, tuneids, limit, dbfile, outdir='.'):
        """Batch download images from the specific tune

        Args:
            tuneids (one or more int): The Astria Tune IDs
            limit (int): Maximum number of prompts to check from each tune
            dbfile (string): Base name of the database file to use for cache
        """
        assert (limit > 0)
        assert (tuneids)

        if not Path(outdir).exists():
            os.mkdir(outdir)

        with shelve.open(dbfile, flag='c') as db:
            for tuneid in tuneids:
                results = 0
                while (1):
                    lastprompts = self.list(tuneid, results)

                    if not lastprompts:
                        break

                    for prompt in lastprompts:
                        id = prompt['id']
                        if str(id) in db:
                            logging.info(f"prompt {tuneid}:{id} already downloaded - skipping")
                        elif prompt['images']:
                            self.downloadPromptImages(tuneid, id, targetdir=Path(outdir,str(tuneid)))
                            db[str(id)] = prompt
                        results = results + 1
                        if (results > limit):
                            break

                    if (results > limit):
                        break


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
            astria.downloadPromptImages(args.tuneid, r['id'], wait=True)

def do_tune(args):
    astria = Astria(args.key)
    
    branch = 'fast' if args.test else ''
  
    result = astria.tune(args.title, args.classname, args.images, args.callback, branch)
    print (json.dumps(result.json(), indent=4))

def do_listtune(args):
    astria = Astria(args.key)
    result = astria.listtune()
    print (json.dumps(result.json(), indent=4))

def do_list(args):
    astria = Astria(args.key)
    result = astria.list(args.tuneid)
    print (json.dumps(result, indent=4))

def do_promptinfo(args):
    astria = Astria(args.key)
    result = astria.promptinfo(args.tuneid, args.promptid)
    print (json.dumps(result.json(), indent=4))

def do_download_prompt_images(args):
    astria = Astria(args.key)
    astria.downloadPromptImages(args.tuneid, args.promptid, args.wait)

def do_download_all_images(args):
    astria = Astria(args.key)

    tunelist = args.tuneids

    if (not tunelist):
        tunes = astria.listtune().json()
        tunelist = {tune['id'] for tune in tunes}

    astria.downloadTuneImages(tunelist, args.limit, args.db, args.outdir)

def environ_or_required(key):
    return (
        {'default': os.environ.get(key)} if os.environ.get(key)
        else {'required': True}
    )


# Command line for Astria
def main() -> int:

    parser = argparse.ArgumentParser(description='Command line tool for Astria',fromfile_prefix_chars='@')
    parser.add_argument('--key', type=str, help='Astria API token', **environ_or_required('ASTRIA_API_TOKEN') )
    parser.add_argument('--callback', type=str, default='')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--outdir', type=str, help='Output directory for images', default=".")

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
    parser_tune.add_argument('classname', type=str, help='Dreambooth classname (style, person, man, woman etc)')
    parser_tune.add_argument('images', nargs='+', type=str, help='At least 10 image filenames')
    parser_tune.add_argument('--test', action='store_true', help='Use fast testing branch')
    parser_tune.set_defaults(func=do_tune)

    parser_list = subparsers.add_parser('list', help='List all generated images for a tune')
    parser_list.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_list.set_defaults(func=do_list)

    parser_list = subparsers.add_parser('listtune', help='List all tunes in the account')
    parser_list.set_defaults(func=do_listtune)

    parser_details = subparsers.add_parser('info', help='Get details of prompt')
    parser_details.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_details.add_argument('promptid', type=int, help='Prompt ID')
    parser_details.set_defaults(func=do_promptinfo)

    parser_download = subparsers.add_parser('download', help='Download images of prompt')
    parser_download.add_argument('tuneid', type=int, help='Astria Tune ID')
    parser_download.add_argument('promptid', type=int, help='Prompt ID')
    parser_download.add_argument('--wait', action='store_true', help='Wait for results to be ready')
    parser_download.set_defaults(func=do_download_prompt_images)

    parser_downloadall = subparsers.add_parser('downloadall', help='Download recent images')
    parser_downloadall.add_argument('tuneids', type=int, nargs='*', help='One or more Astria Tune IDs, or emtpy to download entire account')
    parser_downloadall.add_argument('--limit', type=int, help='Maximum number of prompts to download from each fine tune', default=10)
    parser_downloadall.add_argument('--db', type=str, help='Keep list of previously downloaded images in a DB file', default="astriacache")
    parser_downloadall.set_defaults(func=do_download_all_images)

    args=parser.parse_args()

    logging.getLogger('root').setLevel(logging.INFO)

    # Optional debugging for HTTP requests
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