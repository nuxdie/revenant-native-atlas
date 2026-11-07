.intel_syntax noprefix
.global _render_probe
_render_probe:
 pushfd
 pushad
 mov eax,DWORD PTR [esp+40]
 cmp eax,19
 je record
 cmp eax,20
 je record
 cmp eax,21
 je record
 cmp eax,27
 je record
 cmp eax,14
 jne done
record:
 mov edx,0x77770000
 mov ecx,1
 lock xadd DWORD PTR [edx],ecx
 cmp ecx,65536
 jae done
 shl ecx,4
 lea edi,[edx+ecx+16]
 mov DWORD PTR [edi],eax
 mov eax,DWORD PTR [esp+44]
 mov DWORD PTR [edi+4],eax
 mov eax,DWORD PTR [esp+36]
 mov DWORD PTR [edi+8],eax
 mov eax,DWORD PTR ds:0x62ef14
 test eax,eax
 jz noframe
 mov eax,DWORD PTR [eax+0x48]
noframe:
 mov DWORD PTR [edi+12],eax
done:
 popad
 popfd
 mov eax,DWORD PTR ds:0x5838ec
 push esi
 push 0x415766
 ret
