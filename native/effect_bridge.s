.intel_syntax noprefix
.global _effect_bridge
.extern _effect_blend
_effect_bridge:
 pushfd
 pushad
 push ecx
 call address
address:
 pop eax
 add eax,_effect_blend-address
 call eax
 add esp,4
 popad
 popfd
 /* Relocated original complete instruction, then return to retail code. */
 sub esp,0x118
 push 0x40dd26
 ret
