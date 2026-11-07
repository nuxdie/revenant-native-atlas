.intel_syntax noprefix
.global _shadow_bridge
.extern _shadow_blend
_shadow_bridge:
 mov eax,DWORD PTR [esp+4]
 test DWORD PTR [eax+12],0x20000
 jz original
 mov ecx,DWORD PTR [eax+8]
 and ecx,0xc107
 cmp ecx,0x104
 jne original
 mov edx,DWORD PTR [esp+8]
 test DWORD PTR [edx],0x2000
 jz original
 test DWORD PTR [edx],0x20c40c08
 jnz original
 /* Position independent address, with no imports or loader relocations. */
 call address
 address:
 pop eax
 add eax,_shadow_blend-address
 ret
 original:
 push ebx
 push esi
 mov esi,DWORD PTR [esp+12]
 xor eax,eax
 push edi
 push 0x48edd9
 ret
