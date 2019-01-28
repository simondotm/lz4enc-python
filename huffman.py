# Succinct Huffman encoder with canonical code output
# based on https://github.com/adamldoyle/Huffman
# @simondotm

from heapq import *
import array
from collections import defaultdict


class Huffman:

    def __init__(self):
        self.key = {}
        self.rKey = {}

    def build(self, phrase):
        self.setFrequency(phrase)
        self.buildTree()
        self.buildKey()

    def setFrequency(self, phrase):
        self.frequency = defaultdict(int)
        for c in phrase:
            self.frequency[c] += 1
        

    def buildTree(self):
        self.heap = [[v, k] for k, v in self.frequency.iteritems()]
        heapify(self.heap)
        while len(self.heap) > 1:
            left, right = heappop(self.heap), heappop(self.heap)
            heappush(self.heap, [left[0] + right[0], left, right])

    def buildKey(self, root=None, code=''):
        if root is None:
            self.buildKey(self.heap[0])
            for k,v in self.key.iteritems():
                self.rKey[v] = k
        elif len(root) == 2:
            self.key[root[1]] = code
        else:
            self.buildKey(root[1], code+'0')
            self.buildKey(root[2], code+'1')

    def buildCanonical(self):
        print("Building canonical table")
        self.table = [0] * 256
        for k in self.key:
            self.table[k] = len(self.key[k])
        #print(self.table)



        ktable = [] #[(0,0)] * 256
        for n in range(256):
            if n in self.key:
                ktable.append( (len(self.key[n]), n ) )
            #else:
            #    ktable[n] = (0, n)
        ktable.sort( key=lambda x: (x[0], x[1]) )
        minbits = ktable[0][0]
        maxbits = max(self.table)
        #print("maxbits=" + str(maxbits) + ", minbits=" + str(minbits))

        #print("sorted canonical table")
        #print(ktable)

        self.table_bitlengths = [0]*16
        self.table_symbols = []

        # build the decoder tables
        for k in ktable:
            self.table_bitlengths[k[0]] += 1
            self.table_symbols.append(k[1])
        print("decoder tables (size=" + str(len(self.table_bitlengths)+len(self.table_symbols)) + ")")
        print(self.table_bitlengths)
        print(self.table_symbols)


        newtable = {}
        bitlength = minbits
        code = 0

        #code = 0
        #while more symbols:
        #    print symbol, code
        #    code = (code + 1) << ((bit length of the next symbol) - (current bit length))


        numsymbols = len(ktable)
        for n in range(numsymbols):
            k = ktable[n]
            bitlength = k[0]
            codestring = format(code, '0' + str(bitlength) + 'b')                
            newtable[k[1]] = codestring
            code = (code + 1) 
            if n < (numsymbols - 1):
                code <<= (ktable[n+1][0]-bitlength)
            #print("n=" + str(n) + ", bitlength=" + str(k[0]) + ", symbol=" + str(k[1]) + ", code=" + codestring + ", check=" + str(len(codestring)==bitlength))
        #print(newtable)
 
        for k in self.key:
            self.key[k] = newtable[k]




    def encode(self, phrase):

        print("canonical table")
        self.buildCanonical()

        #print(self.frequency)
        mincodelen = 65536
        maxcodelen = 0
        for v in self.key:
            #print("key=" + str(v) + ", value=" + self.key[v])
            codelen = len(self.key[v])
            mincodelen = min(mincodelen, codelen)
            maxcodelen = max(maxcodelen, codelen)

        #print(" codes from " + str(mincodelen) + " to " + str(maxcodelen) + " bits in length")
        assert maxcodelen < 17

        output = bytearray()
        currentbyte = 0  # The accumulated bits for the current byte, always in the range [0x00, 0xFF]
        numbitsfilled = 0  # Number of accumulated bits in the current byte, always between 0 and 7 (inclusive)

        sz = 0
        for c in phrase:
            k = self.key[c]
            sz += len(k)
            for b in k:
                bit = int(b)
                assert bit == 0 or bit == 1
                currentbyte = (currentbyte << 1) | bit
                numbitsfilled += 1
                if numbitsfilled == 8:
                    output.append(currentbyte)
                    currentbyte = 0
                    numbitsfilled = 0                  

        # align to byte.
        while (numbitsfilled < 8):
            currentbyte = (currentbyte << 1) | 1
            numbitsfilled += 1
        output.append(currentbyte)

        print("calc size=" + str(sz/8))

        #open("z.huf", "wb").write( output ) 
        # test decode
        self.decode(output, phrase)
        return output

    # test decoder
    def decode(self, data, source):
        print("test decode")
        output = bytearray()

        if False:
            code_table = [0] * 256
            code_table2 = []
            bit_table = [0] * 16
            for k in self.key:
                code_size = len(self.key[k])
                code_table[k] = code_size
                code_table2.append(k)
                bit_table[code_size] += 1


            #print(bit_table)
            #print(code_table)
            #print(code_table2)


        # decode the stream
        currentbyte = 0
        bitbuffer = 0
        numbitsbuffered = 0
        code = 0                            # word
        code_size = 0                       # byte

        firstCodeWithNumBits = 0            # word
        startIndexForCurrentNumBits = 0     # byte

        # 6502 workspace
        # (2) stream read ptr (can replace the one used by lz4, so no extra)
        # (2) table_bitlengths - only referenced once, can perhaps be self modified
        # (2) table_symbols - only referenced once, can perhaps be self modified, implied +16 from table_bitlengths
        # (1) bitbuffer
        # (1) bitsleft
        # only needed during symbol fetch
        # (2) code
        # (2) firstCodeWithNumBits
        # (1) startIndexForCurrentNumBits
        # (1) code_size
        # (1) numCodes
        # (1) indexForCurrentNumBits
        # Note that table does not necessarily require 256 bytes now, will contain 16 entries plus N symbols. If few symbols occur.
        # Could be an argument for separate tables per stream if compression ratio beats table overhead.
        # we cant interleave the lz4 data because variable bytes needed per register stream per frame
        # therefore we have to maintain 8 huffman contexts also.

        sourceindex = 0
        while True:

            # keep the bitbuffer going
            if numbitsbuffered == 0:
                # we're out of data, so any wip codes are invalid due to byte padding.
                if currentbyte >= len(data):
                    break

                bitbuffer = data[currentbyte]
                currentbyte += 1
                numbitsbuffered += 8
                

            # get a bit
            bit = (bitbuffer & 128) >> 7
            bitbuffer <<= 1
            numbitsbuffered -= 1

            # build code
            code = (code << 1) | bit
            code_size += 1

            # how many canonical codes have this many bits
            numCodes = self.table_bitlengths[code_size] # byte

            #print("currentbyte=" + str(currentbyte) + ", code_size=" + str(code_size) + ", numcodes=" + str(numCodes) + ", code=" + format(code, '0b') + ", numbitsbuffered=" + str(numbitsbuffered))


            # if input code so far is within the range of the first code with the current number of bits, it's a match
            indexForCurrentNumBits = code - firstCodeWithNumBits
            if indexForCurrentNumBits < numCodes:
                symbol = self.table_symbols[startIndexForCurrentNumBits + indexForCurrentNumBits]
                output.append(symbol)
                expected = source[sourceindex]
                #print(" found symbol " + str(symbol) + ", expected " + str(expected))
                assert symbol == expected
                sourceindex += 1

                code = 0
                code_size = 0

                firstCodeWithNumBits = 0
                startIndexForCurrentNumBits = 0                

            else:
                # otherwise, move to the next bit length
                firstCodeWithNumBits = (firstCodeWithNumBits + numCodes) << 1
                startIndexForCurrentNumBits += numCodes

        assert len(output) == len(source)
        assert output == source
        print("decoded outputsize="+str(len(output)) + ", expected=" + str(len(source)) )
