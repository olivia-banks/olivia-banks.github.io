---
title: Building a Tool to Read Firefox Memory Core Snapshots
date: 2024-07-31
type: page
description: An alternative to the utility that's tangled in the Firefox source tree.
---
**NOTE**: You can find the full code [here](https://git.sr.ht/~oliviabanks/fxsdump).

For some reason, one of my friends has been having issues with Firefox on Asahi Linux. The Discord tab keeps leaking memory, making the browser (and in fact the entire system) nearly unusable. As part of a troubleshooting effort, I asked them to send me the dump file produced by the "Memory" tab in Firefox. I didn’t know what data would be contained in it, but I expected something a little more detailed than [about:memory](about:memory). Instead, what I got was a giant tree of opaque pointers. Still, I figured I’d write about it, since it might be useful to someone.

Firefox includes a tool to parse and look into these files, but it can't be used unless you build it from the Firefox source tree, and I've never been able to get it building for some reason on any of the occasions I've tried. It doesn't help that the only existing 3rd party tool to do this errored out for me, supposedly because the snapshot file was too large. I subsequently built my own, granted very naïve, tool.
## The `.fxsnapshot` format

The `.fxsnapshot` format is just a `.gz` archive that contains some raw binary data. The data is encoded as the length of a message, followed by the binary representation of a message. The binary data of each individual message is some Google Protocol Buffer data, the schema for which can be found in the Firefox source tree. The `CoreDump.proto` handily provides a specification of the file.

<img src="/img/core_dump_layout.svg" style="width: 70%; display: block; margin: 0 auto;"/>

## Implementation
Now let's write a tool to deal with this format, and we'll do it in Python for simplicity. Let's scaffold the program:

```python
import sys

def usage(file):
    print("fxsdump [snapshot]", file=file)

def main():
    if len(sys.argv) != 2:
        usage(sys.stderr)
        exit(1)
    elif sys.argv[1] == '-h':
        usage(sys.stdout)
        return

	input_path = sys.argv[1]
	results = {'metadata': None, 'nodes': []}

	# ...

if __name__ == '__main__':
    main()
```

Great! Let's go ahead and read the file and un`gzip` it.

```python
import gzip

# Inside main().

with gzip.open(input_path, 'rb') as f:
	# ...
```

Before we do much else, we need to define a function to read the message defined in the length-data format used in the snapshot file.

```python
import CoreDump_pb2

def read_varint32(file):
    shift = 0
    result = 0

    while True:
        byte = file.read(1)
        if not byte:
            raise EOFError("Unexpected end of file while reading varint32.")

        byte = ord(byte)
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break

        shift += 7

    return result

def parse_message(file, message_class):
    message_size = read_varint32(file)
    message_data = file.read(message_size)

    message = message_class()
    message.ParseFromString(message_data)

    return message
```

After this, we can go and parse the metadata, then loop through all the messages.

```python
from google.protobuf.json_format import MessageToDict

# Inside the opened gzip file code.

try:
	metadata = parse_message(f, CoreDump_pb2.Metadata)
	results["metadata"] = MessageToDict(metadata)

  while True:
		node = parse_message(f, CoreDump_pb2.Node)
		results["nodes"].append(MessageToDict(node))

except EOFError:
	pass
```

You may notice that we're calling the `MessageToDict` function. This function doesn't have much overhead, and allows us to serialize our result dictionary to a JSON object string so we can dump it to a file. If you were going to do any sort of processing on the snapshot data, you'd probably omit that function and just append the message directly to avoid any sort of overhead.

### YOLO

Regardless, after that we'll go ahead and convert the `result` to a JSON object string, and save it to a file.

```python
import json

# Outside the opened gzip file code.

print(json.dumps(results, indent=4))
```

Before we can run anything, we need to compile the `CoreDump.proto` file so we have the associated utilities available to our script. We'll make a simple Makefile to deal with this:

```make
PROTOC ?= protoc

CoreDump_pb2.py: CoreDump.proto
	$(PROTOC) --python_out=. $<

.PHONY: all
all: CoreDump_pb2.py
```

And why not make a gitignore?

```text
__pycache__/

*.fxsnapshot
*.json
CoreDump_pb2.py
```

Great! Now you can run the Makefile, and then the tool.
## The Full Code

You can find the full code below, or [on sourcehut](https://git.sr.ht/~oliviabanks/fxsdump).

```python
import sys
import gzip
import json
import CoreDump_pb2
from google.protobuf.json_format import MessageToDict

def usage(file):
	print("fxsdump [snapshot]", file=file)

def read_varint32(file):
    shift = 0
    result = 0

    while True:
        byte = file.read(1)
        if not byte:
            raise EOFError("Unexpected end of file while reading varint32.")

        byte = ord(byte)
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break

        shift += 7

    return result

def parse_message(file, message_class):
    message_size = read_varint32(file)
    message_data = file.read(message_size)

    message = message_class()
    message.ParseFromString(message_data)

    return message

def main():
	if len(sys.argv) != 2:
		usage(sys.stderr)
		exit(1)
	elif sys.argv[1] == '-h':
		usage(sys.stdout)
		return

	input_path = sys.argv[1]
	results = {'metadata': None, 'nodes': []}

	with gzip.open(input_path, 'rb') as f:
		try:
			metadata = parse_message(f, CoreDump_pb2.Metadata)
			results["metadata"] = MessageToDict(metadata)

			while True:
				node = parse_message(f, CoreDump_pb2.Node)
				results["nodes"].append(MessageToDict(node))

		except EOFError:
			pass

	with open(input_path + '.json', 'w') as f:
	   f.write(json.dumps(results, indent=4))

if __name__ == '__main__':
	main()
```

Let's test it! I have the original data that my friend sent me saved, so I'll test it on that:

```bash
python fxsdump.py 2450796.fxsnapshot > out.json
```

After a substantial amount of time (a couple of minutes, thanks Python), we get output. I've pipped it into a file so it doesn't wreak havoc.
