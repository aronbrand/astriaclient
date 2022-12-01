# Astria API CLI client and SDK
This is an simple python SDK and CLI for Astria.ai, the DreamBooth based image generation service.

## CLI usage
When used as a command line tool, these are the arguments:

### Suppored actions:
    gen                 Generate images for prompts
    tune                Create a new tune
    list                List all generated images for a tune
    listtune            List all tunes in the account
    info                Get details of prompt
    download            Download images of prompt
    downloadall         Download recent images

Optional arguments:
- --key KEY             Astria API token (if unspecified, token is taken from the enviroment variable ASTRIA_API_TOKEN)
- --outdir OUTDIR       Output directory for images (default is current working directory)
  
 
### Usage for gen action:

python astria.py gen [--seed SEED] [--steps STEPS] [--download]
                     tuneid prompts [prompts ...]

- --seed SEED
- --steps STEPS
- --download     Download results

### Usage for tune action:

python astria.py tune [--test] title classname images [images ...]

    title       Descriptive name for this tuning
    classname   Dreambooth classname (style, person, man, woman etc)
    images      At least 10 image filenames
  
### Usage for list action:
python astria.py list tuneid

### Usage for listtune action:
python astria.py listtune 

### Usage for info action:
python astria.py info tuneid promptid

- tuneid      Astria Tune ID
- promptid    Prompt ID

### Usage for download acation:
python astria.py download [--wait] tuneid promptid
  
- tuneid      Astria Tune ID
- promptid    Prompt ID

  optional arguments:
- --wait      Wait for results to be ready

### Usage for downloadall acation:
python astria.py downloadall [--limit LIMIT] [--db DB] [tuneids ...]
- tuneids        One or more Astria Tune IDs, or emtpy to download entire account

  optional arguments:
- --limit LIMIT  Maximum number of prompts to download from each fine tune
- --db DB        Keep list of previously downloaded images in a DB file

