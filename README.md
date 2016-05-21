# haya-data
Distribution and restoration of information over network.
This software is written by me, for a school project is CS.

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
