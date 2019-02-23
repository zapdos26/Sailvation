import discord
import json
import os

def get(file):
    try:
        fileDir = os.path.dirname(os.path.realpath('__file__'))
        file = os.path.join(fileDir, 'configs/{}'.format(file))
        with open(file, encoding='utf8') as data:
            return json.load(data)
    except AttributeError:
        raise AttributeError("Unknown argument")
    except FileNotFoundError:
        raise FileNotFoundError("JSON file wasn't found")
    
def save(obj,file):
    try: 
        fileDir = os.path.dirname(os.path.realpath('__file__'))
        file = os.path.join(fileDir, 'configs/{}'.format(file))
        with open(file,'w',encoding='utf8') as data:
            json.dump(obj,data,indent=4,sort_keys=True)
        return
    except AttributeError:
        raise AttributeError("Unknown argument")
    except FileNotFoundError:
        raise FileNotFoundError("JSON file wasn't found")    
        
    
    