---
title: Recovering images from a forgotten 1980s format (FaceSaver, 1987)
date: 2024-05-12
type: page
description: A converter for the FaceSaver format, which has almost been lost to time.
---
**NOTE**: You can find the full code [here](https://git.sr.ht/~oliviabanks/face2ppm).

I'm currently looking at old source code. More specifically, I've been playing around with Sprite and trying to get it to compile on modern hardware. Sprite was a UNIX-like experimental distributed operating system developed between 1984 and 1992 at the University of California Berkeley. Sprite was developed with the intent to create a more "network aware," while keeping it invisible to the user. The primary innovation was a new network file system that utilized local client-side caching to enhance performance. Once a file is opened and some initial reads are completed, the network is accessed only on-demand, with most user actions interacting with the cache. Similar mechanisms allow remote devices to be integrated into the local computer's environment, enabling network printing and other similar functions.

Regardless, there's a directory in the source tree called docs/pictures. The README in the directory states:

> This directory contains images of some of the members of the Sprite project.
> These images are in FaceSaver format and may be displayed with `xloadimage`.

I've never heard of anything called FaceSaver before. A quick Google search comes up with [this page on the file format wiki](http://justsolve.archiveteam.org/wiki/FaceSaver), and not much else, which is interesting. Apparently these files are rare! Now to read them.

The file format, being invented in 1987 and not updated (or even really mentioned) since the mid-90s, unsurprisingly doesn't have great support. Attempts to build `xloadimage`, which is old enough to pre-date the Xorg project's use of Autotools and appears to have been relatively untouched for just as long as the FaceSaver format, were unsuccessful on the Linux and NetBSD boxes I tried it on. Neither of the tools the Just Solve wiki suggests, NetBPM and Konverter, could handle them either, although this might be a build issue on my side since I had to preform a myriad of hacks to get them working.

Ultimately, I just really wanted to see inside these photos, so [I found a spec](https://netghost.narod.ru/gff/vendspec/face/face.txt) and implemented a FaceSaver to PPM converter in python, aptly named `face2ppm`. If you aren't familiar with PPM, it's a stupidly simple text-based format for representing raster graphics. The [Wikipedia page for Netpbm](https://en.wikipedia.org/wiki/Netpbm#PBM_example) has some examples.
## Implementation
FaceSaver files are structured with personal data followed by image data. The format includes a header with various fields and the image data encoded in a hexified format. Our goal is to parse these files and convert the image data into a standard PPM (Portable Pixmap) format. The header is in a format like the one below, following by two newlines:

```text
FirstName:
LastName:
E-mail:
Telephone:
Company:
Address1:
Address2:
CityStateZip:
Date:
PicData:         Actual data:  width - height - bits/pixel
Image:           Should be transformed to: width - height - bits/pixel
```

Most of this data we don't care about. I can't imagine why it was included in the format, as it seems that it would be better to maintain an index of every FaceSaver file and it's associated metadata, instead of have instead of looping and parsing every file if you wanted to get the head shot of "Mary Baker". Perhaps for sending photos? Nevertheless, we only care about `PicData` and `Image`. Let's write a parser for the header.

We'll loop through every line in the header, splitting on colons, trimming the whitespace off the string, and then doing further parsing if we need. This is needed in the case of `PicData` and `Image`, which are tuples of width, height, and bits per pixel.

```python
class ImageShape:
    def __init__(self, shape_string):
        parts = shape_string.split(' ')
        self.width = int(parts[0])
        self.height = int(parts[1])
        self.density = int(parts[2])

    def __str__(self):
        return f"width={self.width}, height={self.height}, density={self.density} bpp"

def parse_header(header):
    # Split the header into lines
    lines = header.strip().split('\n')
    parsed_data = {}

    for line in lines:
        key, value = line.split(': ', 1)
        key = key.strip()
        value = value.strip()

        # Check if we need to do further parsing.
        if key == 'PicData' or key == 'Image':
            parsed_data[key] = ImageShape(value)
        else:
            parsed_data[key] = value

    return parsed_data
```

Before we can use this function though, we need to read in the file, extract the header and data (which we can do because they're separated with two newlines), and clean up the data so we can turn it into a byte sequence.

```python
# Read the file.
filename = sys.argv[1]
image_data = None

with open(filename, 'r') as f:
    image_data = f.read()

# Do some header parsing.
sections = image_data.split('\n\n')
header = sections[0]
image = sections[1]

header = parse_header(header)
data_shape = header['PicData']
image_shape = header['Image']

image = image.replace('\n', '')
image = bytes.fromhex(image)
```

After that, we have our image dimensions as well as the raw image bytes. Let's go ahead and write a routine for converting that into a 2D array of colors so we can dump it to disk later.

```python
def bytes_to_rgb_array(byte_sequence, data_shape):
    width = data_shape.width
    height = data_shape.height
    bits_per_pixel = data_shape.density

	  # Do some checks.
    if bits_per_pixel != 8:
        raise ValueError(f"We only support 8 bits per pixel, not {bits_per_pixel}.")

    if len(byte_sequence) != width * height:
        raise ValueError(f"Image data is not as reported, wanted {width * height} " +
            "got {len(byte_sequence)}.")

    # Move stuff around.
    byte_array = list(byte_sequence)[::-1]
    byte_array = np.array(byte_array, dtype=np.uint8).reshape((height, width))
    rgb_array = np.zeros((height, width, 3), dtype=np.uint8)

    # Marshall into colors.
    for y in range(height):
        for x in range(width):
            pixel_value = byte_array[y, x]
            rgb_array[y, x] = (pixel_value, pixel_value, pixel_value)

    rgb_list_of_lists = [[tuple(rgb_array[y, x]) for x in range(width)] for y in range(height)]

    return rgb_list_of_lists
```

It looks a little complicated, but that's likely my lack of idiomatic Python. The first convert byte sequence into an array so NumPy can deal with it, then reverse it with `[::-1]`. This is necessary because the FaceSaver file format specifies that the image pixels are stored in scanlines from bottom to top, so reversing the list corrects the order to top to bottom.

Then, the reversed `byte_array` is converted to a NumPy array and reshaped to the specified height and width. This step creates a 2D array representing the image, but we still need to exact colors. We make space for the colors by calling `np.zeros` to create a new array, then looping over `byte_array`, populating `rgb_array` as we go. The nested loop iterates through each pixel in the byte_array. For each pixel, it retrieves the grayscale pixel_value and sets the corresponding pixel in `rgb_array` to a tuple `(pixel_value, pixel_value, pixel_value)`, effectively converting the grayscale image to an RGB image where R, G, and B values are equal.

Finally, we convert convert the `rgb_array` NumPy array into a list of lists of tuples. Each element in the list is a tuple `(R, G, B)` representing the RGB values of a pixel. We're ready to dump to a PPM file!

```python
# Read the image data to color values.
color_data = bytes_to_rgb_array(image, data_shape)

# Output to PPM.
with open(filename + '.ppm', 'w') as f:
    # Write the PPM header.
    f.write(f'P3\n{data_shape.width} {data_shape.height}\n255\n')

    # Write the pixel data.
    for row in color_data:
        for color in row:
            f.write(f'{color[0]} {color[1]} {color[2]} ')

        f.write('\n')
```

And that's it, we now have a tool which can convert FaceSaver images to PPM files; let's go ahead and test it with some sample FaceSaver files from the Sprite project.

```bash
$ tree .
.
├── jhh
├── mgbaker
├── ouster
└── shirriff

$ find . ! -name "*.*" -exec python face2ppm.py {} ;
$ tree .
.
├── jhh
├── jhh.ppm
├── mgbaker
├── mgbaker.ppm
├── ouster
├── ouster.ppm
├── shirriff
└── shirriff.ppm
```

<div style="display: flex; justify-content: center; align-items: center; margin-left: auto; margin-right: auto; gap: 1.5rem;">
<img src="/img/facesaver-mgbaker.png" alt="A woman with bangs beaming into the camera." />
<img src="/img/facesaver-jhh.png" alt="A man with glasses looking into camera, head tilted slightly." />
<img src="/img/facesaver-ouster.png" alt="A man with parted hair looking directly into the camera, smiling." />
<img src="/img/facesaver-shirriff.png" alt="A man in a patterned shirt, smiling and wearing glasses." />
</div>

## The Full Code
The full code can be found [here](https://git.sr.ht/~oliviabanks/face2ppm), and a shorter version can be found below.

```python
# Utility for converting FaceSaver files into PPM format.
#
# Spec: https://netghost.narod.ru/gff/vendspec/face/face.txt

import sys
import numpy as np

def usage():
    print("usage: face2ppm [file]", file=sys.stderr)

class ImageShape:
    def __init__(self, shape_string):
        parts = shape_string.split(' ')
        self.width = int(parts[0])
        self.height = int(parts[1])
        self.density = int(parts[2])

    def __str__(self):
        return f"width={self.width}, height={self.height}, density={self.density} bpp"

def parse_header(header):
    # Split the header into lines
    lines = header.strip().split('\n')

    # Create an empty dictionary to store the parsed data
    parsed_data = {}

    # Iterate through each line
    for line in lines:
        # Split each line into key and value
        key, value = line.split(': ', 1)
        # Add the key-value pair to the dictionary
        parsed_data[key.strip()] = value.strip()

    return parsed_data

def bytes_to_rgb_array(byte_sequence, data_shape):
    width = data_shape.width
    height = data_shape.height
    bits_per_pixel = data_shape.density

    # Do some checks.
    if bits_per_pixel != 8:
        raise ValueError(f"We only support 8 bits per pixel, not {bits_per_pixel}.")

    if len(byte_sequence) != width * height:
        raise ValueError(f"Image data is not as reported, wanted {width * height} " +
            "got {len(byte_sequence)}.")

    # Move stuff around.
    byte_array = list(byte_sequence)[::-1]
    byte_array = np.array(byte_array, dtype=np.uint8).reshape((height, width))
    rgb_array = np.zeros((height, width, 3), dtype=np.uint8)

    # Marshall into colors.
    for y in range(height):
        for x in range(width):
            pixel_value = byte_array[y, x]
            rgb_array[y, x] = (pixel_value, pixel_value, pixel_value)

    rgb_list_of_lists = [[tuple(rgb_array[y, x]) for x in range(width)] for y in range(height)]

    return rgb_list_of_lists

def main():
    if (len(sys.argv) != 2):
        usage()
        exit(1)

    # Read the file.
    filename = sys.argv[1]
    image_data = None

    with open(filename, 'r') as f:
        image_data = f.read()

    # Do some header parsing.
    sections = image_data.split('\n\n')
    header = sections[0]
    image = sections[1]

    header = parse_header(header)
    data_shape = ImageShape(header['PicData'])
    image_shape = ImageShape(header['Image'])

    image = image.replace('\n', '')

    # Read the image data to color values.
    color_data = bytes_to_rgb_array(bytes.fromhex(image), data_shape)

    # Output to PPM.
    with open(filename + '.ppm', 'w') as f:
        # Write the PPM header
        f.write(f'P3\n{data_shape.width} {data_shape.height}\n255\n')

        # Write the pixel data
        for row in color_data:
            for color in row:
                f.write(f'{color[0]} {color[1]} {color[2]} ')

            f.write('\n')

if __name__ == '__main__':
    main()
```

**Note**
I didn't implement the `Image:` part of the header, because in my experience
every file I've tried this utility on has worked fine, with no stretching. I
don't need this functionality, so I'm not going to implement it.
