#// //////////////////////////////////////////////////////////
#// smallz4.h
#// Copyright (c) 2016-2018 Stephan Brumme. All rights reserved.
#// see https://create.stephan-brumme.com/smallz4/
#//
#// "MIT License":
#// Permission is hereby granted, free of charge, to any person obtaining a copy
#// of this software and associated documentation files (the "Software"),
#// to deal in the Software without restriction, including without limitation
#// the rights to use, copy, modify, merge, publish, distribute, sublicense,
#// and/or sell copies of the Software, and to permit persons to whom the Software
#// is furnished to do so, subject to the following conditions:
#//
#// The above copyright notice and this permission notice shall be included
#// in all copies or substantial portions of the Software.
#//
#// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#// OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#// SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import struct
import os
import sys

from timeit import default_timer as timer
import profile


#pragma once
#include <inttypes.h> // uint16_t, uint32_t, ...
#include <cstdlib>    // size_t
#include <vector>
#/// LZ4 compression with optimal parsing
#/** see smallz4.cpp for a basic I/O interface
#    you can easily replace it by a in-memory version
#    then all you have to do is:
#    #include "smallz4.h"
#    smallz4::lz4(GET_BYTES, SEND_BYTES);
#    // for more advanced stuff, you can call lz4 with four parameters (incl. max chain length and a dictionary)
#**/
class SmallLZ4():
#{
#public:
#  // read  several bytes, see getBytesFromIn() in smallz4.cpp for a basic implementation
#  typedef size_t (*GET_BYTES) (      void* data, size_t numBytes);
#  // write several bytes, see sendBytesToOut() in smallz4.cpp for a basic implementation
#  typedef void   (*SEND_BYTES)(const void* data, size_t numBytes);
#  /// compress everything in input stream (accessed via getByte) and write to output stream (via send)
#  static void lz4(GET_BYTES getBytes, SEND_BYTES sendBytes,
#                  unsigned int maxChainLength = MaxChainLength,
#                  bool useLegacyFormat = false)  // this function exists for compatibility reasons
#  {
#    lz4(getBytes, sendBytes, maxChainLength, std::vector<unsigned char>());
#  }
#  /// compress everything in input stream (accessed via getByte) and write to output stream (via send)
#  static void lz4(GET_BYTES getBytes, SEND_BYTES sendBytes,
#                  unsigned int maxChainLength,
#                  const std::vector<unsigned char>& dictionary, // predefined dictionary
#                  bool useLegacyFormat = false)                 // old format is 7 bytes smaller if input < 8 MB
#  {
#    smallz4 obj(maxChainLength);
#    obj.compress(getBytes, sendBytes, dictionary, useLegacyFormat);
#  }
#  /// version string
  Version = "1.3"
#  static const char* const getVersion()
#  {
#    return "1.3";
#  }
#  // compression level thresholds, made public because I display them in the help screen ...
#  enum
#  {
  #/// greedy mode for short chains (compression level <= 3) instead of optimal parsing / lazy evaluation
  ShortChainsGreedy = 3
  #/// lazy evaluation for medium-sized chains (compression level > 3 and <= 6)
  ShortChainsLazy   = 6
#  };
#  // ----- END OF PUBLIC INTERFACE -----
#private:
  #// ----- constants and types -----
  #/// a block can be 4 MB
  #typedef uint32_t Length;
  #/// matches must start within the most recent 64k
  #typedef uint16_t Distance;
  #/// each match's length must be >= 4
  MinMatch          =  4
  #/// last match must not be closer than 12 bytes to the end
  BlockEndNoMatch   = 12
  #/// last 5 bytes must be literals, no matching allowed
  BlockEndLiterals  =  5
  #/// match finder's hash table size (2^HashBits entries, must be less than 32)
  HashBits          = 20
  #/// input buffer size, can be any number but zero ;-)
  BufferSize     = 64*1024
  #/// maximum match distance
  MaxDistance    = 65535
  #/// marker for "no match"
  NoPrevious     =       0
  #/// stop match finding after MaxChainLength steps (default is unlimited => optimal parsing)
  MaxChainLength = NoPrevious
  #/// significantly speed up parsing if the same byte is repeated a lot, may cause sub-optimal compression
  MaxSameLetter  =   19 + 255*256 #// was: 19 + 255
  #/// refer to location of the previous match (implicit hash chain)
  PreviousSize   = 1 << 16
  #/// maximum block size as defined in LZ4 spec: { 0,0,0,0,64*1024,256*1024,1024*1024,4*1024*1024 }
  #/// I only work with the biggest maximum block size (7)
  #//  note: xxhash header checksum is precalculated only for 7, too
  MaxBlockSizeId = 7
  MaxBlockSize   = 4*1024*1024
  #/// legacy format has a fixed block size of 8 MB
  MaxBlockSizeLegacy = 8*1024*1024

  #//  ----- one and only variable ... -----
  #/// how many matches are checked in findLongestMatch, lower values yield faster encoding at the cost of worse compression ratio
  #unsigned int maxChainLength;
  #//  ----- code -----
  #/// match
  class Match:
  
    def __init__(self):
      #/// length of match
      self.length = 0
      #/// start of match
      self.distance = 0

    #/// true, if long enough
    def isMatch(self):
      return self.length >= SmallLZ4.MinMatch


  
  #/// create new compressor (only invoked by lz4)
  def __init__(self, level = 9):
    if (level >= 9):
      newMaxChainLength = 65536  #// "unlimited" because search window contains only 2^16 bytes 
    else:
      newMaxChainLength = level

    self.maxChainLength = newMaxChainLength
    #// => no limit, but can be changed by setMaxChainLength

  #/// return true, if the four bytes at *a and *b match
  #inline static bool match4(const void* const a, const void* const b)
  #{
  #  return *(const uint32_t*)a == *(const uint32_t*)b;
  #}

  #/// find longest match of data[pos] between data[begin] and data[end], use match chain stored in previous
  # returns a Match object
  #Match findLongestMatch(const unsigned char* const data, 
  #                       size_t pos, size_t begin, size_t end,
  #                       const Distance* const previous) const
  # data - bytearray
  # pos, begin, end - int
  # previous - Distance list/array
  def findLongestMatch(self, data, pos, begin, end, previous):
  
    #/// return true, if the four bytes at data[a] and data[b] match
    def match4(a, b):
      la = struct.unpack('>L', data[a:a+4])[0]
      lb = struct.unpack('>L', data[b:b+4])[0]

      #la = data[0] + data[1] << 8 + data[2] << 16 + data[3] << 24
      #lb = 
      return la == lb
  
    result = self.Match()
    result.length = 1

    #// compression level: look only at the first n entries of the match chain
    stepsLeft = self.maxChainLength

    #// pointer to position that is matched against everything in data
    #const unsigned char* const current = data + pos - begin
    current = pos - begin

    #// don't match beyond this point
    #const unsigned char* const stop    = current + end - pos
    stop    = current + end - pos

    #// get distance to previous match, abort if 0 => not existing
    distance = previous[pos % self.PreviousSize]
    totalDistance = 0
    while (distance != self.NoPrevious):
      #// too far back ?
      totalDistance += distance
      if (totalDistance > self.MaxDistance):
        break

      #// prepare next position
      distance = previous[(pos - totalDistance) % self.PreviousSize]
      
      #// stop searching on lower compression levels
      stepsLeft -= 1
      if (stepsLeft <= 0):
        break

      #// let's introduce a new pointer atLeast that points to the first "new" byte of a potential longer match
      #const unsigned char* const atLeast = current + result.length + 1;
      atLeast = current + result.length + 1

      #// the idea is to split the comparison algorithm into 2 phases
      #// (1) scan backward from atLeast to current, abort if mismatch
      #// (2) scan forward  until a mismatch is found and store length/distance of this new best match
      #// current                  atLeast
      #//    |                        |
      #//    -<<<<<<<< phase 1 <<<<<<<<
      #//                              >>> phase 2 >>>
      #// impossible to find a longer match because not enough bytes left ?
      if (atLeast > stop):
        break
      #// all bytes between current and atLeast shall be identical, compare 4 bytes at once
      #const unsigned char* compare = atLeast - 4
      compare = atLeast - 4


      ok = True
      while (compare > current):

        #// mismatch ?
        if (not match4(compare, compare - totalDistance)):
          ok = False
          break
        
        #// keep going ...
        compare -= 4
        #// note: - the first four bytes always match
        #//       - in the last iteration, compare is either current + 1 or current + 2 or current + 3
        #//       - therefore we compare a few bytes twice => but a check to skip these checks is more expensive
      

      #// mismatch ?
      if (not ok):
        continue

      #// we have a new best match, now scan forward from the end
      compare = atLeast

      #// fast loop: check four bytes at once
      while (compare + 4 <= stop and match4(compare,     compare - totalDistance)):
        compare += 4

      #// slow loop: check the last 1/2/3 bytes
      #while (compare     <  stop and       *compare == *(compare - totalDistance)):
      while (compare < stop and data[compare] == data[compare - totalDistance]):
        compare += 1

      #// store new best match
      #result.distance = Distance(totalDistance)
      result.distance = totalDistance
      #result.length   = Length  (compare - current)
      result.length   = compare - current
    
    return result
  
  #/// create shortest output
  #/** data points to block's begin; we need it to extract literals **/
  #static std::vector<unsigned char> selectBestMatches(const std::vector<Match>& matches,
  #                                                    const unsigned char* const data)
  # returns byte array
  def selectBestMatches(self, matches, data, index):
    #// store encoded data
    result = bytearray()
    #result.reserve(MaxBlockSize)
    #// indices of current literal run
    literalsFrom = 0
    literalsTo   = 0 #// point beyond last literal of the current run
    #// walk through the whole block
    #for (size_t offset = 0; offset < matches.size(); ): #// increment inside of loop
    offset = 0
    while (offset < len(matches)): #// increment inside of loop
    #for offset in range(len(matches)):

      #// get best cost-weighted match
      #Match match = matches[offset]
      match = self.Match()
      match.length = matches[offset].length
      match.distance = matches[offset].distance

      #// if no match, then count literals instead
      if (not match.isMatch()):
      
        #// first literal
        if (literalsFrom == literalsTo):
          literalsFrom = literalsTo = offset

        #// one more literal
        literalsTo += 1
        #// ... and definitely no match
        match.length = 1
      
      offset += match.length

      lastToken = (offset == len(matches))
      #// continue if simple literal
      if (not match.isMatch() and not lastToken):
        continue

      #// emit token
      #// count literals
      numLiterals = literalsTo - literalsFrom

      #// store literals' length
      if (numLiterals < 15):
        token = numLiterals
      else:
        token = 15

      token <<= 4

      #// store match length (4 is implied because it's the minimum match length)
      matchLength = match.length - 4
      if (not lastToken):
        if (matchLength < 15):
          token |= matchLength
        else:
          token |= 15

      #print(token)
      #print(type(token))
      result.append( token ) #struct.pack('B', token) )
      #print(result)

      #// >= 15 literals ? (extra bytes to store length)
      if (numLiterals >= 15):
      
        #// 15 is already encoded in token
        numLiterals -= 15
        #// emit 255 until remainder is below 255
        while (numLiterals >= 255):       
          #result.append( struct.pack('B', 255) )
          result.append(255)
          numLiterals -= 255
        
        #// and the last byte (can be zero, too)
        #result.append( struct.pack('B', numLiterals) )
        result.append(numLiterals)
      
      #// copy literals
      if (literalsFrom != literalsTo):
      
        #result.insert(result.end(), data + literalsFrom, data + literalsTo)
        subset = data[index + literalsFrom:index + literalsTo]
        result.extend( subset )
        literalsFrom = 0
        literalsTo = 0
      
      #// last token doesn't have a match
      if (lastToken):
        break

      #// distance stored in 16 bits / little endian
      #result.append( struct.pack('B', match.distance & 0xFF) )
      result.append( match.distance & 0xFF )
      #result.append( struct.pack('B', (match.distance >> 8) & 0xFF) )
      result.append( (match.distance >> 8) & 0xFF )
      #// >= 15+4 bytes matched (4 is implied because it's the minimum match length)
      if (matchLength >= 15):
        #// 15 is already encoded in token
        matchLength -= 15
        #// emit 255 until remainder is below 255
        while (matchLength >= 255):
          #result.append( struct.pack('B', 255) )
          result.append(255)
          matchLength -= 255
        
        #// and the last byte (can be zero, too)
        #result.append( struct.pack('B', matchLength) )
        result.append(matchLength)
      
    
    return result
  
  #/// walk backwards through all matches and compute number of compressed bytes from current position to the end of the block
  #/** note: matches are modified (shortened length) if necessary **/
  #static void estimateCosts(std::vector<Match>& matches)
  #{
  def estimateCosts(self, matches):
    blockEnd = len(matches)
    #typedef uint32_t Cost
    #// minimum cost from this position to the end of the current block
    #std::vector<Cost> cost(matches.size(), 0)
    cost = [0] * len(matches)
    
    #// "cost" represents the number of bytes needed
    #// backwards optimal parsing
    posLastMatch = blockEnd

    #for (int i = (int)blockEnd - (1 + BlockEndLiterals); i >= 0; i--) #// ignore the last 5 bytes, they are always literals
    for i in range(blockEnd - (1 + self.BlockEndLiterals), 0, -1 ):

      #// watch out for long literal strings that need extra bytes
      numLiterals = posLastMatch - i
      #// assume no match
      minCost = cost[i + 1] + 1
      #// an extra byte for every 255 literals required to store length (first 14 bytes are "for free")
      if (numLiterals >= 15 and (numLiterals - 15) % 255 == 0):
        minCost += 1

      #// if encoded as a literal
      bestLength = 1
      #// analyze longest match
      #Match match = matches[i]
      match = self.Match()
      match.length = matches[i].length
      match.distance = matches[i].distance    
      
      #// match must not cross block borders
      if (match.isMatch() and i + match.length + self.BlockEndLiterals > blockEnd):
        match.length = blockEnd - (i + self.BlockEndLiterals)

      #// try all match lengths (first short ones)
      #for (Length length = MinMatch; length <= match.length; length++):
      for length in range(self.MinMatch, match.length+1):
      
        #// token (1 byte) + offset (2 bytes)
        currentCost = cost[i + length] + 1 + 2

        #// very long matches need extra bytes for encoding match length
        if (length >= 19):
          currentCost += 1 + (length - 19) / 255
        
        #// better choice ?
        if (currentCost <= minCost):
        
          #// regarding the if-condition:
          #// "<"  prefers literals and shorter matches
          #// "<=" prefers longer matches
          #// they should produce the same number of bytes (because of the same cost)
          #// ... but every now and then it doesn't !
          #// that's why: too many consecutive literals require an extra length byte
          #// (which we took into consideration a few lines above)
          #// but we only looked at literals beyond the current position
          #// if there are many literal in front of the current position
          #// then it may be better to emit a match with the same cost as the literals at the current position
          #// => it "breaks" the long chain of literals and removes the extra length byte
          minCost    = currentCost
          bestLength = length
          #// performance-wise, a long match is usually faster during decoding than multiple short matches
          #// on the other hand, literals are faster than short matches as well (assuming same cost)
        
        #// workaround: very long self-referencing matches can slow down the program A LOT
        if (match.distance == 1 and match.length >= self.MaxSameLetter):
        
          #// assume that longest match is always the best match
          #// however, this assumption might not be optimal
          bestLength = match.length
          minCost    = cost[i + match.length] + 1 + 2 + 1 + (match.length - 19) / 255
          break
        
      
      #// remember position of last match to detect number of consecutive literals
      if (bestLength >= self.MinMatch):
        posLastMatch = i

      #// store lowest cost so far
      cost[i] = minCost
      #// and adjust best match
      matches[i].length = bestLength
      if (bestLength == 1):
        matches[i].distance = self.NoPrevious

      #// note: if bestLength is smaller than the previous matches[i].length then there might be a closer match
      #//       which could be more cache-friendly (=> faster decoding)
    
  #--------------------------------------------------------------------------------------------------------------------------------
  #/// compress everything in input stream (accessed via getByte) and write to output stream (via send), improve compression with a predefined dictionary
  #--------------------------------------------------------------------------------------------------------------------------------
  #void compress(GET_BYTES getBytes, SEND_BYTES sendBytes, const std::vector<unsigned char>& dictionary, bool useLegacyFormat) const 
  def compress(self, in_file, out_file, dictionary, useLegacyFormat):

    # write a byte array to the output stream
    def sendBytes(data):
      out_file.write(data)

    # read upto count bytes from the input stream, returned in a new bytearray 'buffer'
    def getBytes(count):
      buffer = bytearray(in_file.read(count))
      return buffer



    #// ==================== write header ====================
    #// magic bytes
    #const unsigned char magic      [4] = { 0x04, 0x22, 0x4D, 0x18 };
    #const unsigned char magicLegacy[4] = { 0x02, 0x21, 0x4C, 0x18 };
    if (useLegacyFormat):
      #sendBytes(magicLegacy, sizeof(magicLegacy));
      sendBytes( bytearray([0x02, 0x21, 0x4C, 0x18]) )
    else:
      #sendBytes(magic,       sizeof(magic));
      sendBytes( bytearray([0x04, 0x22, 0x4D, 0x18]) )
      
      #// flags
      flags = 1 << 6
      sendBytes( struct.pack('B', flags) )

      #// max blocksize
      maxBlockSizeId = self.MaxBlockSizeId << 4
      sendBytes( struct.pack('B', maxBlockSizeId) )
      
      #// header checksum (precomputed)
      checksum = 0xDF
      sendBytes( struct.pack('B', checksum) )
    
    #// ==================== declarations ====================
    #// read the file in chunks/blocks, data will contain only bytes which are relevant for the current block
    data = bytearray()
    #// file position corresponding to data[0]
    dataZero = 0
    #// last already read position
    numRead  = 0
    #// passthru data (but still wrap in LZ4 format)
    uncompressed = (self.maxChainLength == 0)
    #// last time we saw a hash
    HashSize   = 1 << self.HashBits
    NoLastHash = 0x7FFFFFFF
    #std::vector<size_t> lastHash(HashSize, NoLastHash);
    lastHash = [NoLastHash] * HashSize

    HashMultiplier = 22695477 #// taken from https:#//en.wikipedia.org/wiki/Linear_congruential_generator
    HashShift  = 32 - self.HashBits # uint8
    
    #// previous position which starts with the same bytes
    #std::vector<Distance> previousHash (PreviousSize, Distance(NoPrevious)); #// long chains based on my simple hash
    #std::vector<Distance> previousExact(PreviousSize, Distance(NoPrevious)); #// shorter chains based on exact matching of the first four bytes   
    previousHash = [self.NoPrevious] * self.PreviousSize
    previousExact = [self.NoPrevious] * self.PreviousSize
    
    
    #// change buffer size as you like
    buffer = bytearray(self.BufferSize)

    #// first and last offset of a block (next is end-of-block plus 1)
    lastBlock = 0
    nextBlock = 0
    parseDictionary = len(dictionary) > 0
    while (True):
    
      #// ==================== start new block ====================
      #// first byte of the currently processed block (std::vector data may contain the last 64k of the previous block, too)
      #const unsigned char* dataBlock = NULL;
      # dataBlock is an offset now - see below


      #// prepend dictionary
      if (parseDictionary):

        print(" Loading Dictionary...")

        #// prepend exactly 64k
        MaxDictionary = 65536
        if (len(dictionary) < MaxDictionary):
          #// add garbage data
          unused = 65536 - len(dictionary)
          data.extend( bytearray(unused) )
        else:
          #// copy only the most recent 64k of the dictionary
          #data.insert(data.end(), dictionary.begin() + dictionary.size() - MaxDictionary, dictionary.end());
          doffset = len(dictionary) - MaxDictionary
          data.extend( bytearray( dictionary[doffset:]) )

        nextBlock = len(data)
        numRead   = len(data)
      
      #// read more bytes from input
      if useLegacyFormat:
        maxBlockSize = self.MaxBlockSizeLegacy
      else:
        maxBlockSize = self.MaxBlockSize



      while (numRead - nextBlock < maxBlockSize):
      
        #// buffer can be significantly smaller than MaxBlockSize, that's the only reason for this while-block
        #incoming = getBytes(&buffer[0], buffer.size());
        buffer = getBytes(self.BufferSize)
        incoming = len(buffer)
        if (incoming == 0):
          break
        numRead += incoming

        #data.insert(data.end(), buffer.begin(), buffer.begin() + incoming);
        data.extend( buffer )
      
      #// no more data ? => WE'RE DONE !
      if (nextBlock == numRead):
        break

      print(" Processing Block... " + str(numRead>>10) + "Kb, (maxBlockSize=" + str(maxBlockSize>>10) + "Kb, windowSize=" + str(self.MaxDistance>>10) + "Kb)")

      #// determine block borders
      lastBlock  = nextBlock
      nextBlock += maxBlockSize

      #// not beyond end-of-file
      if (nextBlock > numRead):
        nextBlock = numRead

      #// first byte of the currently processed block (std::vector data may contain the last 64k of the previous block, too)
      #dataBlock = &data[lastBlock - dataZero]
      # dataBlock is an offset now rather than a pointer
      dataBlock = lastBlock - dataZero
      blockSize = nextBlock - lastBlock

      #// ==================== full match finder ====================
      print("  Finding matches...")
      #// greedy mode is much faster but produces larger output
      isGreedy = (self.maxChainLength <= self.ShortChainsGreedy)
      #// lazy evaluation: if there is a (match, then try running match finder on next position, too, but not after that
      isLazy   = (isGreedy == False) and (self.maxChainLength <= self.ShortChainsLazy)

      #// skip match finding on the next x bytes in greedy mode
      skipMatches = 0
      #// allow match finding on the next byte but skip afterwards (in lazy mode)
      lazyEvaluation = False

      #// the last literals of the previous block skipped matching, so they are missing from the hash chains
      lookback = dataZero
      if (lookback > self.BlockEndNoMatch and (parseDictionary == False)):
        lookback = self.BlockEndNoMatch

      if (parseDictionary):
        lookback = len(dictionary)

      #// so let's go back a few bytes
      lookback = -lookback

      #// ... but not in legacy mode
      if (useLegacyFormat):
        lookback = 0
  
      #std::vector<Match> matches(blockSize);
      matches = [ self.Match() for i in range(blockSize) ]

      #// find longest matches for each position
      #for (int i = lookback; i < (int)blockSize; i++)
      for i in range(lookback, blockSize):

        # show progress
        if (i & 511) == 0 or i == (blockSize - 1):
          sys.stdout.write("   Scanning block data " + str(int(i*100/(blockSize-1))) + "%...\r")
          sys.stdout.flush()

        #// no matches at the end of the block (or matching disabled by command-line option -0 )
        if (i + self.BlockEndNoMatch > blockSize or uncompressed):
          continue
      
        #// detect self-matching
#        if (i > 0 and dataBlock[i] == dataBlock[i - 1]):
        if (i > 0 and data[dataBlock + i] == data[dataBlock + i - 1]):
          #Match prevMatch = matches[i - 1];
          prevMatch = matches[i - 1]  # Python version of prevMatch is a reference not an instance
          
          #// predecessor had the same match ?
          if (prevMatch.distance == 1 and prevMatch.length > self.MaxSameLetter): #// TODO: handle very long self-referencing matches          
            #// just copy predecessor without further (expensive) optimizations
            #prevMatch.length--;
            #matches[i] = prevMatch;
            matches[i].length = prevMatch.length - 1
            matches[i].distance = prevMatch.distance
            continue
          
        def getLong(buffer, offset):
          end = offset + 4
          buf = buffer[offset:end]
          four = struct.unpack('>L', buf)[0]
          return four

        #// read next four bytes
        #uint32_t four = *(uint32_t*)(dataBlock + i)
        four = getLong(data, dataBlock + i)

        #// convert to a shorter hash
        hash = ((four * HashMultiplier) >> HashShift) & (HashSize - 1)
        
        #// get last occurrence of these bits
        last = lastHash[hash]
        
        #// and store current position
        lastHash[hash] = i + lastBlock
        
        #// remember: i could be negative, too
        prevIndex = (i + self.PreviousSize) % self.PreviousSize
        
        #// no predecessor or too far away ?
        distance = i + lastBlock - last
        if (last == NoLastHash or distance > self.MaxDistance):
          previousHash[prevIndex] = self.NoPrevious
          previousExact[prevIndex] = self.NoPrevious
          continue
        
        #// build hash chain, i.e. store distance to last match
        previousHash[prevIndex] = distance

        #// skip pseudo-matches (hash collisions) and build a second chain where the first four bytes must match exactly
        while (distance != self.NoPrevious):
          #uint32_t curFour = *(uint32_t*)(&data[last - dataZero]); #// may be in the previous block, too
          curFour = getLong(data, last - dataZero)  #// may be in the previous block, too

          #// actual match found, first 4 bytes are identical
          if (curFour == four):
            break

          #// prevent from accidently hopping on an old, wrong hash chain
          #uint32_t curHash = ((curFour * HashMultiplier) >> HashShift) & (HashSize - 1);
          curHash = ((curFour * HashMultiplier) >> HashShift) & (HashSize - 1)
          if (curHash != hash):
            distance = NoPrevious
            break
          
          #// try next pseudo-match
          next = previousHash[last % self.PreviousSize]

          #// pointing to outdated hash chain entry ?
          distance += next

          if (distance > self.MaxDistance):
            previousHash[last % self.PreviousSize] = self.NoPrevious
            distance = self.NoPrevious
            break
          
          #// closest match is out of range ?
          last -= next
          if (next == self.NoPrevious or last < dataZero):
            distance = self.NoPrevious
            break
          
        
        #// no match at all ?
        if (distance == self.NoPrevious):
          previousExact[prevIndex] = self.NoPrevious
          continue
        
        #// store distance to previous match
        previousExact[prevIndex] = distance

        #// no matching if crossing block boundary, just update hash tables
        if (i < 0):
          continue

        #// skip match finding if in greedy mode
        if (skipMatches > 0):
          skipMatches -= 1
          if (not lazyEvaluation):
            continue

          lazyEvaluation = False
        
        #// and look for longest match
        #print(" Finding longest matches...")

        #Match longest = findLongestMatch(&data[0], i + lastBlock, dataZero, nextBlock - BlockEndLiterals + 1, &previousExact[0]);
        longest = self.findLongestMatch(data, i + lastBlock, dataZero, nextBlock - self.BlockEndLiterals + 1, previousExact)
        matches[i] = longest

        #// no match finding needed for the next few bytes in greedy/lazy mode
        if (longest.isMatch() and (isLazy or isGreedy)):
          lazyEvaluation = (skipMatches == 0)
          skipMatches = longest.length
        
      
      #// dictionary applies only to the first block
      parseDictionary = False
      
      #// ==================== estimate costs (number of compressed bytes) ====================
      print("")
      print("  Estimating costs...")

      #// not needed in greedy mode and/or very short blocks
      if (len(matches) > self.BlockEndNoMatch and self.maxChainLength > self.ShortChainsGreedy):
        self.estimateCosts(matches)

      #// ==================== select best matches ====================
      print("  Selecting best matches...")
      
      #std::vector<unsigned char> block;
      block = bytearray()
      if (not uncompressed):
        #block = selectBestMatches(matches, &data[lastBlock - dataZero]);
        block = self.selectBestMatches(matches, data, lastBlock - dataZero )
      
      #// ==================== output ====================
      #// automatically decide whether compressed or uncompressed
      uncompressedSize = nextBlock - lastBlock

      #// did compression do harm ?
      useCompression   = len(block) < uncompressedSize and not uncompressed

      print(" Writing output block - uncompressed (" + str(uncompressedSize) + "), compressed (" + str(len(block)) + ") ...")
      if useCompression:
        print("  Compressed data selected for this block.")
      else:
        print("  Uncompressed data selected for this block.")

      #// legacy format is always compressed
      if useLegacyFormat:
        useCompression = True
      
      #// block size
      #uint32_t numBytes = uint32_t(useCompression ? block.size() : uncompressedSize);
      if useCompression:
        numBytes = len(block)
      else:
        numBytes = uncompressedSize

      #uint32_t numBytesTagged = numBytes | (useCompression ? 0 : 0x80000000);
      numBytesTagged = numBytes
      if (not useCompression):
        numBytesTagged |= 0x80000000

      #unsigned char num1 =  numBytesTagged         & 0xFF; sendBytes(&num1, 1);
      num1 =  numBytesTagged         & 0xFF
      sendBytes( struct.pack('B', num1) )
      #unsigned char num2 = (numBytesTagged >>  8)  & 0xFF; sendBytes(&num2, 1);
      num2 = (numBytesTagged >>  8)  & 0xFF
      sendBytes( struct.pack('B', num2) )
      #unsigned char num3 = (numBytesTagged >> 16)  & 0xFF; sendBytes(&num3, 1);
      num3 = (numBytesTagged >> 16)  & 0xFF
      sendBytes( struct.pack('B', num3) )
      #unsigned char num4 = (numBytesTagged >> 24)  & 0xFF; sendBytes(&num4, 1);
      num4 = (numBytesTagged >> 24)  & 0xFF
      sendBytes( struct.pack('B', num4) )
      
      if (useCompression):
        #sendBytes(&block[0], numBytes);
        sendBytes(block)
      else: #// uncompressed ? => copy input data
        #sendBytes(&data[lastBlock - dataZero], numBytes);
        index = lastBlock - dataZero
        sendBytes( data[index:index + numBytes] )

      #// legacy format: no matching across blocks
      if (useLegacyFormat):
        dataZero += len(data)
        data = bytearray()

        #// clear hash tables
        #for (size_t i = 0; i < previousHash.size(); i++)
        for i in range(len(previousHash)):
          previousHash[i] = self.NoPrevious
          previousExact[i] = self.NoPrevious

        #for (size_t i = 0; i < lastHash.size(); i++)
        for i in range(len(lastHash)):
          lastHash[i] = self.NoLastHash
    
      else:
      
        #// remove already processed data except for the last 64kb which could be used for intra-block matches
        if (len(data) > self.MaxDistance):
          remove = len(data) - self.MaxDistance
          dataZero += remove
          #data.erase(data.begin(), data.begin() + remove);
          data = data[remove:]

    #// add an empty block
    if (not useLegacyFormat):
      #uint32_t zero = 0
      sendBytes(struct.pack('i', 0))
    

#-------------------------
# main()
#-------------------------

def main():

  start_time = timer()  

  argv = sys.argv
  argv.append("test2.txt")

  print("smallz4 V" + str(SmallLZ4.Version) + ": compressor with optimal parsing, fully compatible with LZ4 by Yann Collet (see https://lz4.org)")
  print("Written in 2016-2018 by Stephan Brumme https://create.stephan-brumme.com/smallz4/")
  print("")
  if len(argv) == 1:
    print("Basic usage:")
    print("  smallz4 [flags] [input] [output]")
    print("")
    print("This program writes to STDOUT if output isn't specified")
    print("and reads from STDIN if input isn't specified, either.")
    print("")
    print("Examples:")
    print("  smallz4   < abc.txt > abc.txt.lz4    # use STDIN and STDOUT")
    print("  smallz4     abc.txt > abc.txt.lz4    # read from file and write to STDOUT")
    print("  smallz4     abc.txt   abc.txt.lz4    # read from and write to file")
    print("  cat abc.txt | smalLZ4 - abc.txt.lz4  # read from STDIN and write to file")
    print("  smallz4 -6  abc.txt   abc.txt.lz4    # compression level 6 (instead of default 9)")
    print("  smallz4 -f  abc.txt   abc.txt.lz4    # overwrite an existing file")
    print("  smallz4 -f7 abc.txt   abc.txt.lz4    # compression level 7 and overwrite an existing file")
    print("")
    print("Flags:")
    print("  -0, -1 ... -9   Set compression level, default: 9 (see below)")
    print("  -h              Display this help message")
    print("  -f              Overwrite an existing file")
    print("  -l              Use LZ4 legacy file format")
    print("  -D [FILE]       Load dictionary")
    print("")
    print("Compression levels:")
    print(" -0               No compression")
    print(" -1 ... -" + str(SmallLZ4.ShortChainsGreedy) +"        Greedy search, check 1 to " + str(SmallLZ4.ShortChainsGreedy) + " matches")
    print(" -" + str(SmallLZ4.ShortChainsGreedy+1) + " ... -8        Lazy matching with optimal parsing, check " + str(SmallLZ4.ShortChainsGreedy+1) + " to 8 matches")
    print(" -9               Optimal parsing, check all possible matches (default)")
    print("")
    sys.exit()


  src = argv[1] 
  compression_level = 9
  dst = src + ".lz4"


  if not os.path.isfile(src):
    print("ERROR: File '" + src + "' not found")
    sys.exit()

  # Pass compression level to compressor
  #  "Compression levels:\n"
  #    " -0               No compression\n"
  #    " -1 ... -%d        Greedy search, check 1 to %d matches\n"
  #    " -%d ... -8        Lazy matching with optimal parsing, check %d to 8 matches\n"
  #    " -9               Optimal parsing, check all possible matches (default)\n"



  print("Compressing file '" + src + "' to '" + dst + "', using compression level " + str(compression_level) )

  compressor = SmallLZ4(compression_level)
  file_in = open(src, 'rb')
  file_out = open(dst, 'wb')
  compressor.compress(file_in, file_out, bytearray(), False)
  file_in.close()
  file_out.close()

  src_size = os.path.getsize(src)
  dst_size = os.path.getsize(dst)
  if src_size == 0:
    ratio = 0
  else:
    ratio = 100 - (int)((dst_size / src_size)*100)

  print(" Input file " + str(src_size) + " bytes, Output file " + str(dst_size) + ", (" + str(ratio) + "% compression)" )

  end_time = timer()

  print("Completed in " + str(end_time-start_time) + "s.")

#--------------------------------


if True:
  main()
else:
  profile.run('main()')

#m = SmallLZ4.Match()
#print(m.isMatch())
#m.length = 56
#print(m.isMatch())
