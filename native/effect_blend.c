/* Compatibility for the June 1999 loose geyser resources. They omit a
 * blendcont for black-backed mesh quads. PartSys temporarily assigns litadd
 * to templates, then restores their saved default when it closes. Applying
 * the native policy only to the base misses those restored template quads.
 * No texture, position, animation, particle or lighting values are changed. */
typedef unsigned int U;
void effect_surface(U type,U count,U index,U* flags,U* mode){
 if(!((type==0x730019 && count==5 && index<5)||
      (type==0x720019 && count==3 && index<3)))return;
 /* Respect explicit nondefault blend policies, including authored ones. */
 if((*mode&~0x40u)!=0 && (*mode&~0x40u)!=0x10)return;
 *flags|=0x01000000;
 *mode=(*mode&0x40)|0x10;
}
#ifndef EFFECT_HOST_TEST
void effect_blend(void* animator){
 U* a=(U*)animator;
 if(!a||a[0]!=0x55669c||!a[1])return;
 U type=((U*)a[1])[1],count=a[0x44/4];
 if(!((type==0x730019&&count==5)||(type==0x720019&&count==3))||!a[0x54/4])return;
 for(U index=0;index<count;++index){
  U* object=(U*)((U*)a[0x54/4])[index];
  if(object&&object[1]==index)effect_surface(type,count,index,object,object+0x324/4);
 }
}
#endif
