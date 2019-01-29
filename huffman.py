# Succinct Huffman encoder with canonical code output
# based on https://github.com/adamldoyle/Huffman
# @simondotm

from heapq import *
import array
from collections import defaultdict

# Notes about this implementation:
#  1) It does not support EOF huffman codes. This makes it simpler for use with 8-bit/byte based alphabets.
#     Instead we transmit the unpacked size as an indicator for how many symbols exist in the file. We also transmit the number of padding bits.
#  2) We only support huffman code sizes upto and including 16 bits in length.

class Huffman:

    MAX_CODE_BIT_LENGTH = 20
    MAX_SYMBOLS = 256

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

    # from the previously calculated huffman tree
    # compute canonical versions of the huffman codes
    def buildCanonical(self):
        print("Building canonical table")
        #self.table = [0] * Huffman.MAX_SYMBOLS
        #for k in self.key:
        #    self.table[k] = len(self.key[k])
        ##print(self.table)


        # convert the tree to an array of (bitlength, symbol) tuples
        ktable = []
        for n in range(Huffman.MAX_SYMBOLS):
            if n in self.key:
                ktable.append( (len(self.key[n]), n ) )

        # sort them into bitlength then symbol order
        ktable.sort( key=lambda x: (x[0], x[1]) )

        # get bit range
        minbits = ktable[0][0]
        maxbits = ktable[-1][0] # max(self.table)
        assert minbits > 0
        assert maxbits <= Huffman.MAX_CODE_BIT_LENGTH
        #print("maxbits=" + str(maxbits) + ", minbits=" + str(minbits))

        #print("sorted canonical table")
        #print(ktable)

        # create a local table for the sorted bitlengths and tables
        self.table_bitlengths = [0] * (Huffman.MAX_CODE_BIT_LENGTH+1)
        self.table_symbols = []

        # build the tables needed for decoding 
        # - an array where array[n] is the number of symbols with bitlength n
        # - an array of the symbols, in ascending order 
        for k in ktable:
            self.table_bitlengths[k[0]] += 1
            self.table_symbols.append(k[1])

        #print("decoder tables (size=" + str(len(self.table_bitlengths)+len(self.table_symbols)) + ")")
        #print(self.table_bitlengths)
        #print(self.table_symbols)



        #code = 0
        #while more symbols:
        #    print symbol, code
        #    code = (code + 1) << ((bit length of the next symbol) - (current bit length))

        # now we build the canonical codes, replacing the previously calculated codes as we go.
        #newtable = {}
        bitlength = minbits
        code = 0
        numsymbols = len(ktable)
        for n in range(numsymbols):
            k = ktable[n]
            bitlength = k[0]
            codestring = format(code, '0' + str(bitlength) + 'b') # convert the code to a binary format string, leading zeros set to bitlength                
            #newtable[k[1]] = codestring
            self.key[k[1]] = codestring
            code = (code + 1) 
            if n < (numsymbols - 1):
                code <<= ( ktable[n+1][0] - bitlength )
            #print("n=" + str(n) + ", bitlength=" + str(k[0]) + ", symbol=" + str(k[1]) + ", code=" + codestring + ", check=" + str(len(codestring)==bitlength))
        #print(newtable)
 
        ## replace the previously calculated codes with the new canonical codes.
        #for k in self.key:
        #    self.key[k] = newtable[k]




    def encode(self, phrase, blockHeader = True, tableHeader = True):

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

        print(" codes from " + str(mincodelen) + " to " + str(maxcodelen) + " bits in length")
        assert maxcodelen <= Huffman.MAX_CODE_BIT_LENGTH

        output = bytearray()

        if blockHeader:
            # emit optional 4 byte header
            # 4 bytes unpacked size with top 3 bits being number of wasted bits in the stream. 
            # this informs the decoder of the size of the uncompressed stream (ie. number of symbols to decode) and how many bits were wasted
            num_symbols = len(phrase)
            print("num_symbols=" + str(num_symbols))
            output.append( num_symbols & 255 )
            output.append( (num_symbols >> 8) & 255 )
            output.append( (num_symbols >> 16) & 255 )
            output.append( ((num_symbols >> 24) & 31) )

        # send the header for decoding
        if tableHeader:
            # 1 byte symbol count
            # We could compute this as the sum of the non-zero bitlengths.  
            output.append( len(self.table_symbols) ) # size of symbol table            
        
            # emit N bytes for the code bit lengths (ie. the number of symbols that have a code of the given bit length)
            assert len(self.table_bitlengths) == (Huffman.MAX_CODE_BIT_LENGTH+1)

            # We exploit the fact that no codes have a bit length of zero, so we use that field to transmit how long the bit length table is (in bytes)
            # This way we have a variable length header, and transmit the minimum amount of header data.
            self.table_bitlengths[0] = maxcodelen #len(self.table_symbols)
            for n in range(maxcodelen+1):
                output.append(self.table_bitlengths[n])
            #for n in self.table_bitlengths:
            #    output.append(n)

            # emit N bytes for the symbols table
            for n in self.table_symbols:
                output.append(n & 255)

        # huffman encode and transmit the data stream
        currentbyte = 0  # The accumulated bits for the current byte, always in the range [0x00, 0xFF]
        numbitsfilled = 0  # Number of accumulated bits in the current byte, always between 0 and 7 (inclusive)

        sz = 0
        # for each symbol in the input data, fetch the assigned code and emit it to the output bitstream
        for c in phrase:
            k = self.key[c]
            sz += len(k)
            for b in k:
                bit = int(b)
                assert bit == 0 or bit == 1
                currentbyte = (currentbyte << 1) | bit
                numbitsfilled += 1
                if numbitsfilled == 8:  # full byte, flush to output
                    output.append(currentbyte)
                    currentbyte = 0
                    numbitsfilled = 0                  

        # align to byte. we could emit code >7 bits in length to prevent decoder finding a spurious code at the end, but its likely
        # some data sets may contain codes <7 bits. Easier to just pad wasted bytes.
        wastedbits = (8 - numbitsfilled) & 7
        print("wastedbits=" + str(wastedbits))
        while (numbitsfilled < 8) and wastedbits:
            currentbyte = (currentbyte << 1) | 1
            numbitsfilled += 1
        output.append(currentbyte)

        if blockHeader:
            # set wastedbits on the blockheader
            output[3] |= (wastedbits << 5)


        print("output size=" + str(len(output)))

        open("z.huf", "wb").write( output ) 
        #open("z.hufsrc", "wb").write( phrase ) 

        # test decode
        self.decode(output, phrase)
        return output

    # test decoder
    def decode(self, data, source):
        print("test decode")

        # read the header

        # get the unpacked size - this tells us how many symbols to decode
        unpacked_size = data[0] + (data[1]<<8) + (data[2]<<16) + ((data[3] & 31)<<24) # uncompressed size
        print("unpacked_size=" + str(unpacked_size))
        wastedbits = data[3] >> 5

        
        symbol_table_size = data[4]      # fetch the number of symbols in the symbol table
        length_table_size = data[5] + 1  # fetch the number of entries in the bit length table (+1 because we include zero)

        length_table = data[5:5+length_table_size]
        symbol_table = data[5+length_table_size:5+length_table_size+symbol_table_size]

        # decode the stream
        currentbyte = 5 + length_table_size + symbol_table_size

        output = bytearray()

        bitbuffer = 0
        numbitsbuffered = 0
        code = 0                            # word
        code_size = 0                       # byte

        firstCodeWithNumBits = 0            # word
        startIndexForCurrentNumBits = 0     # byte

        # 6502 workspace - assuming max 16-bit codes
        # init
        # (2) table_bitlengths - only referenced once, can perhaps be self modified
        # (2) table_symbols - only referenced once, can perhaps be self modified, implied +16 from table_bitlengths
        # per stream
        # (2) stream read ptr (can replace the one used by lz4, so no extra)
        # (1) bitbuffer
        # (1) bitsleft
        # per symbol fetch
        # (2) code
        # (2) firstCodeWithNumBits
        # (1) startIndexForCurrentNumBits
        # (1) code_size
        # (1) numCodes
        # (1) indexForCurrentNumBits
        # Note that table does not necessarily require MAX_SYMBOLS bytes now, will contain 16 entries plus N symbols. If few symbols occur.
        # Could be an argument for separate tables per stream if compression ratio beats table overhead.
        # we cant interleave the lz4 data because variable bytes needed per register stream per frame
        # therefore we have to maintain 8 huffman contexts also.

        sourceindex = 0

        unpacked = 0
        while unpacked < unpacked_size: # currentbyte < len(data):

            # keep the bitbuffer going
            if numbitsbuffered == 0:
                # we're out of data, so any wip codes are invalid due to byte padding.
                #if currentbyte >= len(data):
                #    break

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
            assert code_size <= Huffman.MAX_CODE_BIT_LENGTH
            numCodes = length_table[code_size] # self.table_bitlengths[code_size] # byte

            #print("currentbyte=" + str(currentbyte) + ", code_size=" + str(code_size) + ", numcodes=" + str(numCodes) + ", code=" + format(code, '0b') + ", numbitsbuffered=" + str(numbitsbuffered))


            # if input code so far is within the range of the first code with the current number of bits, it's a match
            indexForCurrentNumBits = code - firstCodeWithNumBits
            if indexForCurrentNumBits < numCodes:
                code = startIndexForCurrentNumBits + indexForCurrentNumBits

                symbol = symbol_table[code] #self.table_symbols[startIndexForCurrentNumBits + indexForCurrentNumBits]
                output.append(symbol)
                expected = source[sourceindex]
                assert symbol == expected
                sourceindex += 1

                code = 0
                code_size = 0

                firstCodeWithNumBits = 0
                startIndexForCurrentNumBits = 0      

                unpacked += 1          

                #print(" found symbol n=" + str(unpacked) + ", " + str(symbol) + ", expected " + str(expected))

            else:
                # otherwise, move to the next bit length
                firstCodeWithNumBits = (firstCodeWithNumBits + numCodes) << 1
                startIndexForCurrentNumBits += numCodes

        assert len(output) == len(source)
        assert output == source
        print("decoded outputsize="+str(len(output)) + ", expected=" + str(len(source)) )
