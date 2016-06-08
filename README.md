# haya-data
Distribution and restoration of information over network.
This software is written by me, for a school project of CS.

haya-data is networked system for distributing files over non reliable client.
the user operate the system from the GUI in the server.

### Features
  * Distribute file with custom parameters over network
  * Restore the file from the clients
  * View the state of the distributed data blocks by client, or by file
  * Initialize system reconstruction that fixes damaged and corrupted data

### Requirements
  * Windows 7+ **or** linux
  * Python 2.7
  * pygtk

All other dependencies is included in the project.

### Usage
The system is designed that the server and the clients can be started and shutdown independently.

##### Starting the server
Example starting server that listens on port 3016
```sh
$ python main.py -p 3016
```

##### Starting the client
Example starting client that connects to server 192.168.0.1 on port 3016
```sh
$ python main.py -p 3016 -s 192.168.0.1
```

### Internal structure
TODO explenation on the algorithms.

### Performence
Currently the system is extremely slow. Distributing a file of 1MB can take 1-3 minutes.
It depends of the used settings.

### Future plans
##### Turn it into a library
I mainly plan to change the interface of distributing and restoring file,
to implement a file-like object. This will make it possible to incorporate
the system into other project, and make it truly usable.

This means that The distribution and restoration module basically stays the same.
I want to entirely change the inter-thread communication, get rid of the ugly
queue based messaging.

Next, I want to add a hooks framework, that will allow the developer to add custom callbacks.
After I will add the hooks, I will decouple the GUI from the rest of the system.

This changes are basically means transforming the system into a generic library,
and then add the GUI as a separated frontend.

##### Change the reconstruction process
I want to entirely rewrite the reconstruction thread. Instead of global reconstruction thread,
There will be a reconstruction thread per file. A global system reconstruction will be just
starting a reconstruction thread to each file in the storage.

### Thanks
I owe a big thanks to Merry Geva and Eran Feri, my teachers, that helped me all the way to the end.
