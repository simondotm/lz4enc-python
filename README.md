# lz4enc-python
Python port of [Stephan Brumme's Smallz4 LZ4 encoder](https://create.stephan-brumme.com/smallz4/)

[@simondotm](https://github.com/simondotm) / 2019 

## About

This project came about as I was in need of a decent compression algorithm that had the following characteristics:
* Fast decompression
* Simple compression algorithm
* Byte oriented output stream
* Reasonable compression ratios
* Minimum or no decoder side memory buffer requirements
* Suited for embedded/8-bit CPUs
* Has possibility for 'streamed' decompression
* Tweakable for my own nefarious purposes.

My aim was to take an existing algorithm and customize it for use on some 8-bit 6502 code/data. LZ4 fit the requirements perfectly, and so since I like working in Python I decided to port Stephan's implementation to Python directly from the C++ source.

**WARNING:** It's REALLY SLOW in Python if you use the full optimal parser, but... it suits my needs since I'm only working with small data sets.

There are two Python scripts in this project - `smallz4.py` which is a direct line-by-line port of Stephan's `smalllz4` `.cpp/.h` source files. Stephan provides an excellent analysis of how the encoding and decoding techniques work.

The second script is `lz4enc.py` which is a more general purpose variant for use with Python - and has API changes to allow more flexible use of LZ4 compression within other Python based tool chains.




## Release Notes

### `smallz4.py`

The code isn't guaranteed to be bug free, but so far it checks out! Feel free to make use of it.

The only change I made was to allow a command line parameter to override the default maximum LZ4 compression "window size" of 65,335 bytes. It's useful for comparison purposes to be able to change this to smaller sizes. LZ4 stores match offsets in 16-bits so using a smaller window does mean the data storage is less efficient, but retains byte stream compatibility.

#### Usage


```
smallz4 V1.3: compressor with optimal parsing, fully compatible with LZ4 by Yann Collet (see https://lz4.org)
Written in 2016-2018 by Stephan Brumme https://create.stephan-brumme.com/smallz4/
Python port 2019 by Simon M, https://github.com/simondotm/

usage: smallz4.py [-h] [-o OUTPUT] [-D file] [-c int] [-f] [-l] [-p]
                  [-w WINDOW] [-v]
                  input

positional arguments:
  input                 read from file [input]

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        write to file [output] (default is '[input].lz4'
  -D file, --dict file  Load dictionary file
  -c int, --compress int
                        Set compression level (0-9), default: 9
  -f, --force           Overwrite an existing file
  -l, --legacy          Use LZ4 legacy file format
  -p, --profile         Profile the script
  -w WINDOW, --window WINDOW
                        Set LZ4 window size, default:65535
  -v, --verbose         Enable verbose mode

Compression levels:
 -0               No compression
 -1 ... -3        Greedy search, check 1 to 3 matches
 -4 ... -8        Lazy matching with optimal parsing, check 4 to 8 matches
 -9               Optimal parsing, check all possible matches (default)
```

### `lz4enc.py`

`lz4enc.py` is a more general purpose version of `smallz4.py` intended for use as an imported class interface. The API isn't fancy, it was designed to suit my own needs.

#### Usage

Importing:
```
from lz4enc import LZ4
```

Setting the compression parameters:
```
LZ4.setCompression( [int] compressionLevel, [int] windowSize = 65535)
```


Compressing a bytearray input buffer to a compressed LZ4 file output bytearray, complete with frames:
```
[bytearray] output = LZ4.compress( [bytearray] inputData, [bytearray] dictionary = bytearray())
```

Emit an LZ4 compatible frame header to the outputBuffer bytearray.
```
LZ4.beginFrame( [bytearray] outputBuffer)
```

Compressing a bytearray input buffer to a compressed LZ4 block output byte array, optionally using dictionary as a seed for the encoder.
```
LZ4.compressBlock( [bytearray] inputData, [bytearray] dictionary = bytearray())
```
Emit an LZ4 compatible frame end signal (a block with size 0) to the outputBuffer
```
LZ4.endFrame( [bytearray] outputBuffer)
```

#### Example

```

from lz4enc import LZ4 

output = bytearray()

compressor = LZ4()
level = 9
window = 65535
compressor.setCompression(level, window)

compressor.beginFrame(output)

block_in = open(input_filename, "rb").read()

dictionary = bytearray()

block_out = compressor.compressBlock(block_in, dictionary)

output.extend(block_out)


compressor.endFrame(output)

open(output_filename, "wb").write(output)

```



## General Notes

#### LZ4 Notes
LZ4 is simple. LZ4 is fast. It also can offer decent compression.

It uses 64Kb sliding windows, which is fine if you are unpacking in place because the sliding window is the previously decoded stream.

Byte streaming is possible by allowing a 'fetch byte' routine that pulls from the decoded stream window up until the history point, at which point more decoding is required.
If byte streaming isnt needed, the history buffer is not required since the decoded stream represents that buffer and for 8-bit machines a 64Kb window is fine.

LZ4 uses 64Kb windows because the match offset field is 16-bits. In principle the encoder can be modified to use a smaller match distance without breaking compatibility.

LZ4 also supports dictionaries, in so much that they are prepended to the history window at the start of compression & decompression to give them context of available matches.
This is very useful for small files that contain repetitive or common phrases, since small files typically dont compress well due to the fact they dont have much data to build a dictionary.

#### Other considerations

Exomiser is great at compression, but it is slow(er) and a complex file format.
ZStandard is interesting, but the implementation is complex.
LZW uses dictionary tables rather than sliding windows, and not suited to low power/memory CPU environments.

LZO/LZMO are other variants I looked at, but settled on LZ4.

## References

### LZ4

* [Smallz4 home page](https://create.stephan-brumme.com/smallz4/), explanations of the LZ4 algorithm and encoding/decoding techniques
* [Official LZ4 Home Page](https://lz4.github.io/lz4/)
* [LZ4 Github repo](https://github.com/lz4/lz4)
* [LZ4 Command Line Man Page](https://www.systutorials.com/docs/linux/man/1-lz4/)
* [Useful article on dictionary-based compression](http://fastcompression.blogspot.com/2018/02/when-to-use-dictionary-compression.html)
* [Great Explanation of LZ4 decompression (and other compression methods suited to older hardware)](http://www.brutaldeluxe.fr/products/crossdevtools/lz4/index.html)
* LZ4 file format - [Frame format](https://github.com/lz4/lz4/blob/dev/doc/lz4_Frame_format.md), [Block format](https://github.com/lz4/lz4/blob/dev/doc/lz4_Block_format.md)

### Lizard/LZ5
* If you are interested in how LZ4 can be improved (better compression but with similar high performance decompression) take a look at [Lizard (was LZ5)](https://github.com/inikep/lizard)

All credit and thanks to Stephan for his excellent work providing such excellent and useful resources for LZ4 encoding and decoding.
