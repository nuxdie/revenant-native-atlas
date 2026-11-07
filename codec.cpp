// Bounded port of Cinematix's ChunkDecompress / ChunkDecompressZ
// in benjcooley/Revenant/chunkcache.cpp (source attribution in CREDITS.md).
// LZ copies literal bytes from the COMPRESSED SOURCE, as the original ESI
// instructions do. It does not refer into the decompressed destination.
#include <cstddef>
#include <cstdint>
#include <algorithm>
extern "C" int rev_chunk(const uint8_t* src, size_t size, size_t start,
                          uint16_t* out, int depth) {
    if (start + 6 > size) return -1;
    std::fill(out, out+4096, depth ? 0x7f7f : 0);
    const uint8_t dl=src[start+4], dh=src[start+5];
    size_t i=start+6, d=0; int rows=0, high=0;
    while (rows<64) {
        if (i>=size) return -2;
        uint8_t v=src[i++];
        if (v==dl) {
            if (i>=size) return -2;
            unsigned n=src[i++];
            if (!n) {++rows; continue;}
            if (n&128) {d+=n&127; if(d>4096)return depth?1:-3; continue;}
            if(i>=size)return -2;
            if(d+n>4096){if(!depth)return -3;std::fill(out+std::min(d,size_t(4096)),out+4096,uint16_t(src[i]+(high<<8)));return 1;}
            std::fill(out+d,out+d+n,uint16_t(src[i++]+(depth ? high<<8 : 0)));d+=n;
        } else if(v==dh) {
            if(i>=size)return -2;
            unsigned n=src[i++];
            if(depth && n==0) {if(i>=size)return -2;high=src[i++];continue;}
            if(i+2>size)return -2;
            unsigned dist=src[i]+(src[i+1]<<8);i+=2;
            if(i<dist+4)return -4;
            bool clip=d+n>4096;
            if(clip&&!depth)return -3;
            n=std::min(size_t(n),size_t(4096)-std::min(d,size_t(4096)));
            size_t p=i-dist-4;
            if(p<start+6 || p+n>size)return -4;
            for(unsigned k=0;k<n;++k)out[d++]=src[p+k]+(depth?high<<8:0);
            if(clip)return 1;
        } else {
            if(d>=4096)return depth?1:-3;
            out[d++]=v+(depth?high<<8:0);
        }
    }
    return d==4096 ? 0 : -5;
}
