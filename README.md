# lz4enc-python
Python port of [Stephan Brumme's Smallz4 LZ4 encoder].(https://create.stephan-brumme.com/smallz4/)

[@simondotm](https://github.com/simondotm) / 2019 

## About

This project came about as I was in need of a decent compression algorithm that had the following characteristics:
* Fast decompression
* Simple compression algorithm
* Byte oriented output stream
* Minimum or no decoder side memory buffer requirements
* Tweakable for my own nefarious purposes.

My aim was to take an existing algorithm and customize it for use on some 8-bit 6502 code/data. LZ4 fit the requirements perfectly, and so since I like working in Python I decided to port Stephan's implementation to Python directly from the C++ source.

**WARNING:** It's REALLY SLOW in Python! But... it suits my needs since I'm only working with small data sets.

## Notes

The code isn't guaranteed to be bug free, but so far it checks out! Feel free to make use of it.



## References

* [Smallz4](https://create.stephan-brumme.com/smallz4/)
* [LZ4 Man Page](https://www.systutorials.com/docs/linux/man/1-lz4/)
* [LZ4 Home Page](https://github.com/lz4/lz4)
* [Dictionary compression](http://fastcompression.blogspot.com/2018/02/when-to-use-dictionary-compression.html)

All credit and thanks to Stephan for his excellent work providing such excellent and useful resources for LZ4 encoding and decoding.
