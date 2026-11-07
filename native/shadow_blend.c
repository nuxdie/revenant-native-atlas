/* Correct the retail RGB565 alpha -> ARGB1555 background-texture mismatch.
 * Only black, uncompressed shadow bitmaps use this path. Everything else
 * retains the retail dispatcher. No shadow pixels are removed or synthesized
 * after capture. The 15-bit channel rounding follows colortable.cpp.
 */
typedef unsigned int U32;
typedef unsigned short U16;
typedef unsigned char U8;
typedef struct {
 void *srcbitmap,*dstsurface;
 U32 srcflags,dstflags;
 U16 *dest,*dzbuffer,*dnormals;
 int dbufwidth,dbufheight,dstride,dzstride;
 U16 *source,*szbuffer,*snormals;
 int sbufwidth,sbufheight,sstride,szstride;
 void *palette;
 U8 *alpha,*alias;
 U32 keycolor;
} DrawBlock;
typedef struct {
 U32 mode;
 void *func,*callback,*data;
 int ox,oy,cx,cy,cw,ch,dx,dy,dw,dh,sx,sy,sw,sh;
 U32 color,intensity;
 U16 zpos,normal;
} DrawParam;

#ifndef SHADOW_HOST_TEST
typedef char DrawBlockLayoutMustMatchRetail[(sizeof(DrawBlock)==88)?1:-1];
typedef char DrawParamLayoutMustMatchRetail[(sizeof(DrawParam)==84)?1:-1];
#endif

U16 shadow_pixel(U16 d,U32 alpha) {
 if(!alpha)return d;
 U32 k=31-alpha;
 U32 r=((d>>10)&31)*k/31;
 U32 gh=(((d>>8)&3)<<3)*k/31;
 U32 gl=((d>>5)&7)*k/31;
 U32 b=(d&31)*k/31;
 return (U16)((d&0x8000)|(r<<10)|((gh+gl)<<5)|b);
}

int shadow_blend(DrawBlock *db,DrawParam *dp) {
 /* The caller already clips into individual non-wrapping rectangles. */
 if(dp->sw<1||dp->sh<1||dp->dw<1||dp->dh<1||!db->alpha||!db->source||!db->dest)return 0;
 int flipx=(dp->mode&0x80)!=0,flipy=(dp->mode&0x40)!=0;
 /* Stay within the black-shadow correction even if another imagery asset
    happens to share its bitmap flags. */
 for(int y=0;y<dp->sh;++y) {
  int sy=dp->sy+(flipy?dp->sh-1-y:y);
  for(int x=0;x<dp->sw;++x)
   if(db->source[sy*db->sstride+dp->sx+x]) {
    int (*original)(DrawBlock*,DrawParam*)=(void*)(__UINTPTR_TYPE__)(dp->intensity<31?0x495fa0:0x495160);
    return original(db,dp);
   }
 }
 U32 modifier=dp->intensity<31?31-dp->intensity:0;
 for(int y=0;y<dp->sh;++y) {
  int sy=dp->sy+(flipy?dp->sh-1-y:y);
  U16 *dst=db->dest+(dp->dy+dp->oy+y)*db->dstride+dp->dx+dp->ox;
  U8 *alpha=db->alpha+sy*db->sstride+dp->sx;
  for(int x=0;x<dp->sw;++x) {
   U32 a=alpha[flipx?dp->sw-1-x:x];
   if(a>31)a=31;
   a=a>modifier?a-modifier:0;
   dst[x]=shadow_pixel(dst[x],a);
  }
 }
 return 1;
}
