/* Editor control, visibility, and a narrow shadow pixel-format correction.
 * Addresses are pinned to native/provider.json and checked before writes. */
typedef void* HANDLE; typedef void* HWND; typedef unsigned long DWORD;
void* memcpy(void* destination,const void* source,unsigned size){
 volatile unsigned char* d=destination;const volatile unsigned char* s=source;
 for(unsigned i=0;i<size;++i)d[i]=s[i];return destination;
}
void* memset(void* destination,int value,unsigned size){
 volatile unsigned char* d=destination;
 for(unsigned i=0;i<size;++i)d[i]=(unsigned char)value;return destination;
}
#define API __declspec(dllimport) __stdcall
API HWND FindWindowA(const char*,const char*);
API DWORD GetWindowThreadProcessId(HWND,DWORD*);
API long SendMessageA(HWND,unsigned,DWORD,long);
API long GetWindowLongA(HWND,int);
API char* GetCommandLineA(void);
API DWORD GetModuleFileNameA(HANDLE,char*,DWORD);
API HANDLE OpenProcess(DWORD,int,DWORD);
API int ReadProcessMemory(HANDLE,const void*,void*,DWORD,DWORD*);
API int WriteProcessMemory(HANDLE,void*,const void*,DWORD,DWORD*);
API void* VirtualAllocEx(HANDLE,void*,DWORD,DWORD,DWORD);
API int VirtualFreeEx(HANDLE,void*,DWORD,DWORD);
API int VirtualProtectEx(HANDLE,void*,DWORD,DWORD,DWORD*);
API int FlushInstructionCache(HANDLE,const void*,DWORD);
API HANDLE GetCurrentProcess(void);
API int DuplicateHandle(HANDLE,HANDLE,HANDLE,HANDLE*,DWORD,int,DWORD);
API int SetEvent(HANDLE);
API HANDLE CreateFileA(const char*,DWORD,DWORD,void*,DWORD,DWORD,HANDLE);
API int ReadFile(HANDLE,void*,DWORD,DWORD*,void*);
API int WriteFile(HANDLE,const void*,DWORD,DWORD*,void*);
API int CloseHandle(HANDLE);
API void Sleep(DWORD);
API HANDLE OpenThread(DWORD,int,DWORD);
API DWORD SuspendThread(HANDLE);
API DWORD ResumeThread(HANDLE);
API void ExitProcess(unsigned);
static char directory[1024];
static HANDLE observed=0;
static DWORD retiredPid=0,retiredIndex=0;
static void* retiredCommands[16];
static void* traceAllocation=0;
static void path(char* out,const char* name){DWORD i=0,j=0;while(directory[i]){out[i]=directory[i];++i;}while(name[j])out[i++]=name[j++];out[i]=0;}
static void output(const char* name,const void* bytes,DWORD size){
 char filename[1100];DWORD n=0;path(filename,name);
 HANDLE f=CreateFileA(filename,0x40000000,7,0,2,128,0);
 WriteFile(f,bytes,size,&n,0);CloseHandle(f);
}
static void report(DWORD code,DWORD sequence){
 DWORD state[18]={0x41544c53,code,0,0,0,0,0,0,0,0,sequence,0,0,0,0,0,0,0},n=0;
 if(observed){
  ReadProcessMemory(observed,(void*)0x62e480,&state[2],4,&n);
  ReadProcessMemory(observed,(void*)0x62e48c,&state[3],12,&n);
  ReadProcessMemory(observed,(void*)0x62e41c,&state[6],8,&n);
  ReadProcessMemory(observed,(void*)0x62f054,&state[8],4,&n);
  ReadProcessMemory(observed,(void*)0x44f32d,&state[9],1,&n);
  DWORD guard=0;ReadProcessMemory(observed,(void*)0x4125ad,&guard,1,&n);state[9]|=guard<<8;
  ReadProcessMemory(observed,(void*)0x62eff8,&state[11],4,&n);
  DWORD screen=0;ReadProcessMemory(observed,(void*)0x62ef14,&screen,4,&n);
  if(screen)ReadProcessMemory(observed,(void*)(screen+0x48),&state[12],4,&n);
  ReadProcessMemory(observed,(void*)0x625200,&state[13],4,&n);
  ReadProcessMemory(observed,(void*)0x62eab0,&state[14],4,&n);
  ReadProcessMemory(observed,(void*)0x62eab4,&state[15],4,&n);
  ReadProcessMemory(observed,(void*)0x62eacc,&state[16],4,&n);
  state[17]=screen;
 }
 DWORD rendering[4]={0x53484457,sequence,0,0};
 if(observed){
  unsigned char hook[9],prefix[11];
  if(ReadProcessMemory(observed,(void*)0x48edd0,hook,9,&n)&&hook[0]==0xe9){
   rendering[3]=0x48edd5+*(DWORD*)(hook+1);
   unsigned char expected[11]={0x8b,0x44,0x24,0x04,0xf7,0x40,0x0c,0x00,0x00,0x02,0x00};
   if(ReadProcessMemory(observed,(void*)rendering[3],prefix,11,&n)){
    rendering[2]=1;for(int i=0;i<11;++i)if(prefix[i]!=expected[i])rendering[2]=0;
   }
  }
 }
 output("control-rendering.bin",rendering,sizeof(rendering));
 DWORD effects[4]={0x47455953,sequence,0,0};
 if(observed){
  unsigned char hook[6],code[33];
  if(ReadProcessMemory(observed,(void*)0x40dd20,hook,6,&n)&&hook[0]==0xe9){
   effects[3]=0x40dd25+*(DWORD*)(hook+1);
   if(ReadProcessMemory(observed,(void*)effects[3],code,33,&n)&&n==33&&
      code[0]==0x9c&&code[1]==0x60&&code[2]==0x51&&
      code[21]==0x81&&code[22]==0xec&&*(DWORD*)(code+23)==0x118&&
      code[27]==0x68&&*(DWORD*)(code+28)==0x40dd26&&code[32]==0xc3)effects[2]=1;
  }
 }
 output("control-effects.bin",effects,sizeof(effects));
 output("control-state.bin",state,sizeof(state));
 char msg[3]={(char)('0'+code/10),(char)('0'+code%10),10};output("control-result.txt",msg,3);
}
static DWORD execute(const char* text,DWORD length){
 char command[256];if(length>253)return 16;
 for(DWORD i=0;i<length;++i)command[i]=text[i];command[length++]=10;command[length]=0;
 if(observed){CloseHandle(observed);observed=0;}
 HWND h=FindWindowA(0,"Revenant");if(!h)return 2;
 DWORD pid=0,n=0;GetWindowThreadProcessId(h,&pid);
 HANDLE process=OpenProcess(0x478,0,pid);if(!process)return 3;observed=process;
 unsigned char signature[6],expected[6]={0xff,0x15,0xf4,0x60,0x55,0};
 if(!ReadProcessMemory(process,(void*)0x43aeab,signature,6,&n)||n!=6)return 14;
 for(int i=0;i<6;++i)if(signature[i]!=expected[i])return 15;
 if(command[0]=='@'){
  if(command[1]=='e'&&command[2]=='f'){
   unsigned char original[6]={0x81,0xec,0x18,0x01,0,0},existing[6];
   if(!ReadProcessMemory(process,(void*)0x40dd20,existing,6,&n)||n!=6)return 18;
   static unsigned char program[4096];DWORD bytes=0;void* code=0;
   if(command[9]!='o'){
    static char filename[1100];path(filename,"effect-blend-code.bin");
    HANDLE f=CreateFileA(filename,0x80000000,7,0,3,128,0);if(f==(HANDLE)-1)return 18;
    ReadFile(f,program,sizeof(program),&bytes,0);CloseHandle(f);if(!bytes||bytes>=sizeof(program))return 18;
    if(existing[0]==0xe9){
     DWORD target=0x40dd25+*(DWORD*)(existing+1);static unsigned char installed[4096];
     if(!ReadProcessMemory(process,(void*)target,installed,bytes,&n)||n!=bytes)return 12;
     for(DWORD i=0;i<bytes;++i)if(installed[i]!=program[i])return 12;
     return 0;
    }
    for(int i=0;i<6;++i)if(existing[i]!=original[i])return 12;
    code=VirtualAllocEx(process,0,bytes,0x3000,0x40);if(!code)return 7;
    if(!WriteProcessMemory(process,code,program,bytes,&n)||n!=bytes)return 8;
    FlushInstructionCache(process,code,bytes);
   }else if(existing[0]!=0xe9){for(int i=0;i<6;++i)if(existing[i]!=original[i])return 12;return 0;}
   DWORD tid=GetWindowThreadProcessId(h,&pid);HANDLE thread=OpenThread(2,0,tid);if(!thread)return 13;
   unsigned char hook[6]={0xe9,0,0,0,0,0x90};*(DWORD*)(hook+1)=(DWORD)code-0x40dd25;
   DWORD protection=0;SuspendThread(thread);
   int ok=VirtualProtectEx(process,(void*)0x40dd20,6,0x40,&protection);
   if(ok){ok=WriteProcessMemory(process,(void*)0x40dd20,code?hook:original,6,&n)&&n==6;
    FlushInstructionCache(process,(void*)0x40dd20,6);VirtualProtectEx(process,(void*)0x40dd20,6,protection,&protection);}
   ResumeThread(thread);CloseHandle(thread);return ok?0:13;
  }
  if(command[1]=='v'){
   unsigned char original[6]={0x83,0x78,0x08,0x01,0x75,0x65},existing[6];
   if(!ReadProcessMemory(process,(void*)0x4125ad,existing,6,&n))return 18;
   if(existing[0]!=0xe9)for(int i=0;i<6;++i)if(existing[i]!=original[i])return 12;
   DWORD protection=0;if(!VirtualProtectEx(process,(void*)0x4125ad,6,0x40,&protection))return 13;
   WriteProcessMemory(process,(void*)0x4125ad,original,6,&n);FlushInstructionCache(process,(void*)0x4125ad,6);
   VirtualProtectEx(process,(void*)0x4125ad,6,protection,&protection);return 0;
  }
  if(command[1]=='b'){
   unsigned char original[9]={0x53,0x56,0x8b,0x74,0x24,0x0c,0x33,0xc0,0x57},existing[9];
   if(!ReadProcessMemory(process,(void*)0x48edd0,existing,9,&n))return 18;
   if(command[7]=='o') {
    DWORD protection=0;VirtualProtectEx(process,(void*)0x48edd0,9,0x40,&protection);
    WriteProcessMemory(process,(void*)0x48edd0,original,9,&n);FlushInstructionCache(process,(void*)0x48edd0,9);
    VirtualProtectEx(process,(void*)0x48edd0,9,protection,&protection);return 0;
   }
   if(existing[0]!=0xe9)for(int i=0;i<9;++i)if(existing[i]!=original[i])return 12;
   char filename[1100];path(filename,"shadow-blend-code.bin");
   HANDLE f=CreateFileA(filename,0x80000000,7,0,3,128,0);if(f==(HANDLE)-1)return 18;
   static unsigned char program[8192];DWORD bytes=0;ReadFile(f,program,8192,&bytes,0);CloseHandle(f);
   if(!bytes||bytes>=8192)return 18;
   if(existing[0]==0xe9){
    DWORD target=0x48edd5+*(DWORD*)(existing+1);static unsigned char installed[8192];
    if(!ReadProcessMemory(process,(void*)target,installed,bytes,&n)||n!=bytes)return 12;
    for(DWORD i=0;i<bytes;++i)if(installed[i]!=program[i])return 12;
    return 0;
   }
   void* code=VirtualAllocEx(process,0,bytes,0x3000,0x40);if(!code)return 7;
   if(!WriteProcessMemory(process,code,program,bytes,&n))return 8;
   FlushInstructionCache(process,code,bytes);
   DWORD codeProtection=0;VirtualProtectEx(process,code,bytes,0x20,&codeProtection);
   unsigned char hook[9]={0xe9,0,0,0,0,0x90,0x90,0x90,0x90};*(DWORD*)(hook+1)=(DWORD)code-0x48edd5;
   DWORD protection=0;VirtualProtectEx(process,(void*)0x48edd0,9,0x40,&protection);
   WriteProcessMemory(process,(void*)0x48edd0,hook,9,&n);FlushInstructionCache(process,(void*)0x48edd0,9);
   VirtualProtectEx(process,(void*)0x48edd0,9,protection,&protection);return 0;
  }
  if(command[1]=='m'){
   DWORD address=0,size=0;int at=8;
   while(command[at]==' ')++at;
   for(;command[at]!=' '&&command[at]!=10;++at){
    char c=command[at];DWORD digit=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:16;
    if(digit>15)return 16;address=address*16+digit;
   }
   while(command[at]==' ')++at;
   for(;command[at]!=10;++at){if(command[at]<'0'||command[at]>'9')return 16;size=size*10+command[at]-'0';if(size>1048576)return 16;}
   static unsigned char buffer[1048576];
   if(!size||!ReadProcessMemory(process,(void*)address,buffer,size,&n)||n!=size)return 18;
   output("control-memory.bin",buffer,size);return 0;
  }
  if(command[1]=='t'&&command[2]=='r'){
   unsigned char original[8]={0x56,0x55,0xff,0xd7,0x8b,0x54,0x24,0x1c};
   if(command[7]=='r'){
    static unsigned char rows[16+128*184];
    if(!traceAllocation||!ReadProcessMemory(process,traceAllocation,rows,sizeof(rows),&n))return 18;
    output("alpha-trace.bin",rows,sizeof(rows));return 0;
   }
   if(command[7]=='s'&&command[9]=='o'){
    DWORD protection=0;VirtualProtectEx(process,(void*)0x48ed87,8,0x40,&protection);
    WriteProcessMemory(process,(void*)0x48ed87,original,8,&n);FlushInstructionCache(process,(void*)0x48ed87,8);
    VirtualProtectEx(process,(void*)0x48ed87,8,protection,&protection);return 0;
   }
   unsigned char existing[8];
   if(!ReadProcessMemory(process,(void*)0x48ed87,existing,8,&n))return 18;
   for(int i=0;i<8;++i)if(existing[i]!=original[i])return 12;
   char filename[1100];path(filename,"alpha-trace-code.bin");
   HANDLE f=CreateFileA(filename,0x80000000,7,0,3,128,0);if(f==(HANDLE)-1)return 18;
   unsigned char program[512];DWORD bytes=0;ReadFile(f,program,512,&bytes,0);CloseHandle(f);
   if(!bytes||bytes>=512)return 18;
   traceAllocation=VirtualAllocEx(process,0,65536,0x3000,0x40);if(!traceAllocation)return 7;
   for(DWORD i=0;i+4<=bytes;++i){DWORD value=*(DWORD*)(program+i);if(value>=0x77770000&&value<0x77770100){*(DWORD*)(program+i)=value-0x77770000+(DWORD)traceAllocation;i+=3;}}
   void* code=(char*)traceAllocation+32768;
   if(!WriteProcessMemory(process,code,program,bytes,&n))return 8;
   unsigned char hook[8]={0xe9,0,0,0,0,0x90,0x90,0x90};*(DWORD*)(hook+1)=(DWORD)code-0x48ed8c;
   DWORD protection=0;VirtualProtectEx(process,(void*)0x48ed87,8,0x40,&protection);
   WriteProcessMemory(process,(void*)0x48ed87,hook,8,&n);FlushInstructionCache(process,(void*)0x48ed87,8);
   VirtualProtectEx(process,(void*)0x48ed87,8,protection,&protection);return 0;
  }
  if(command[1]=='t'){
   DWORD minute=0;int found=0;
   for(DWORD i=6;i+1<length;++i){if(command[i]<'0'||command[i]>'9')return 16;minute=minute*10+command[i]-'0';found=1;}
   if(!found||minute>1439)return 16;
   WriteProcessMemory(process,(void*)0x625200,&minute,4,&n);return 0;
  }
  if(command[1]=='a'){
   DWORD count=0,list=0,used=0;static DWORD rows[4096*10];
   ReadProcessMemory(process,(void*)0x591bd0,&count,4,&n);
   ReadProcessMemory(process,(void*)0x591be0,&list,4,&n);
   if(count>4096)return 18;
   for(DWORD i=0;i<count;++i){
    DWORD animator=0,object=0;
    if(!ReadProcessMemory(process,(void*)(list+4*i),&animator,4,&n)||!animator)continue;
    if(!ReadProcessMemory(process,(void*)(animator+4),&object,4,&n)||!object)continue;
    rows[used++]=object;
    if(!ReadProcessMemory(process,(void*)object,rows+used,9*4,&n))return 18;
    used+=9;
   }
   output("control-animators.bin",rows,used*4);return 0;
  }
  if(command[1]=='f'||command[1]=='n'){
   DWORD fast=command[1]=='f';WriteProcessMemory(process,(void*)0x62f090,&fast,4,&n);return 0;
  }
  if(command[1]=='g'||command[1]=='d'){
   DWORD mode=command[1]=='g';
   WriteProcessMemory(process,(void*)0x62eff8,&mode,4,&n);return 0;
  }
  if(command[1]=='w'){
   DWORD screen=0,first=0,current=0,quiet=0xffffffff;
   if(!ReadProcessMemory(process,(void*)0x62ef14,&screen,4,&n)||!screen)return 18;
   if(!ReadProcessMemory(process,(void*)(screen+0x48),&first,4,&n))return 18;
   for(int count=0;count<2400;++count){
    Sleep(5);ReadProcessMemory(process,(void*)(screen+0x48),&current,4,&n);
    DWORD pending=0,queued=0,updating=0,rects=0,bg=0;
    ReadProcessMemory(process,(void*)0x62e4d8,&pending,4,&n);
    ReadProcessMemory(process,(void*)0x62ea18,&queued,4,&n);
    ReadProcessMemory(process,(void*)0x601614,&updating,4,&n);
    ReadProcessMemory(process,(void*)0x601628,&rects,4,&n);
    ReadProcessMemory(process,(void*)0x62e514,&bg,4,&n);
    if(pending||queued||updating||rects||bg){quiet=0xffffffff;continue;}
    if(quiet==0xffffffff)quiet=current;
    if(current-first>=4&&current-quiet>=2)return 0;
   }
   return 19;
  }
  if(command[1]=='p'){
   /* Presentation-only capture configuration: background rendering,
      every frame drawn, and no mouse overlay. World rendering is untouched. */
   DWORD pause=0,skip=1;
   WriteProcessMemory(process,(void*)0x5838e4,&pause,4,&n);
   WriteProcessMemory(process,(void*)0x62efec,&skip,4,&n);
   /* The original editor pans whenever the desktop pointer reaches an edge.
      Atlas cameras belong to the controller, including during background
      capture. Keep only the four edge-scroll stores at zero; leave cursor,
      selection and world/rendering code intact. EBX is zero at these stores. */
   DWORD edges[4]={0x448cfe,0x448d0e,0x448d1e,0x448d2e};
   for(int i=0;i<4;++i){
    unsigned char expected[6]={0x89,(i&1)?0xbe:0x96,(i<2)?0x10:0x14,1,0,0},existing[6];
    if(!ReadProcessMemory(process,(void*)edges[i],existing,6,&n)||n!=6)return 18;
    for(int j=0;j<6;++j)if(existing[j]!=expected[j]&&!(j==1&&existing[j]==0x9e))return 12;
    DWORD protection=0;unsigned char zeroStore=0x9e;
    if(!VirtualProtectEx(process,(void*)edges[i],6,0x40,&protection))return 13;
    WriteProcessMemory(process,(void*)(edges[i]+1),&zeroStore,1,&n);FlushInstructionCache(process,(void*)edges[i],6);
    VirtualProtectEx(process,(void*)edges[i],6,protection,&protection);
   }
   DWORD noScroll[2]={0,0};WriteProcessMemory(process,(void*)0x62e4f8,noScroll,8,&n);
   DWORD addresses[2]={0x435d80,0x435ea0};
   unsigned char expectedFirst[2]={0x8b,0xa1},ret=0xc3;
   for(int i=0;i<2;++i){
    unsigned char existing=0;DWORD protection=0;
    if(!ReadProcessMemory(process,(void*)addresses[i],&existing,1,&n)||(existing!=expectedFirst[i]&&existing!=0xc3))return 12;
    if(!VirtualProtectEx(process,(void*)addresses[i],1,0x40,&protection))return 13;
    WriteProcessMemory(process,(void*)addresses[i],&ret,1,&n);FlushInstructionCache(process,(void*)addresses[i],1);
    VirtualProtectEx(process,(void*)addresses[i],1,protection,&protection);
   }
   return 0;
  }
  if(command[1]=='c'){
   DWORD context[4]={(DWORD)GetWindowLongA(h,-4),0,0,0};
   ReadProcessMemory(process,(void*)0x625200,&context[1],4,&n);
   ReadProcessMemory(process,(void*)0x6015dc,&context[2],4,&n);
   ReadProcessMemory(process,(void*)0x624ae4,&context[3],4,&n);
   output("control-context.bin",context,sizeof(context));return 0;
  }
  if(command[1]=='i')return 0;
  if(command[1]=='e'){
   DWORD active=0,yes=1;ReadProcessMemory(process,(void*)0x6015dc,&active,4,&n);
   if(!active)WriteProcessMemory(process,(void*)0x6015dc,&yes,4,&n);
   SendMessageA(h,0x100,123,1);SendMessageA(h,0x101,123,1);
   if(!active)WriteProcessMemory(process,(void*)0x6015dc,&active,4,&n);
   Sleep(80);return 0;
  }
  if(command[1]=='s'||command[1]=='r'){
   DWORD key=command[1]=='r'?82:119;
   DWORD active=0,yes=1;
   ReadProcessMemory(process,(void*)0x6015dc,&active,4,&n);
   WriteProcessMemory(process,(void*)0x6015dc,&yes,4,&n);
   SendMessageA(h,0x100,17,1);SendMessageA(h,0x100,key,1);SendMessageA(h,0x101,key,1);SendMessageA(h,0x101,17,1);
   WriteProcessMemory(process,(void*)0x6015dc,&active,4,&n);return 0;
  }
  if(command[1]=='h'){
   DWORD addresses[3]={0x44f32d,0x44f3ce,0x44f5cb};unsigned char opcode=0xeb;
   for(int i=0;i<3;++i){
    unsigned char existing=0;DWORD protection=0;
    if(!ReadProcessMemory(process,(void*)addresses[i],&existing,1,&n)||(existing!=0x74&&existing!=0xeb))return 12;
    if(!VirtualProtectEx(process,(void*)addresses[i],1,0x40,&protection))return 13;
    WriteProcessMemory(process,(void*)addresses[i],&opcode,1,&n);FlushInstructionCache(process,(void*)addresses[i],1);
    VirtualProtectEx(process,(void*)addresses[i],1,protection,&protection);
   }
   /* The 3D scene has its own visibility check. Apply the gameplay filter
      (INVISIBLE | EDITOR) there too; editor AI and all rasterization stay
      unchanged. The guard clobbers no registers and returns to that loop. */
   unsigned char old[10]={0xf6,0x47,0x08,0x80,0x0f,0x85,0x3f,0x03,0,0},byte=0;
   ReadProcessMemory(process,(void*)0x4125e8,&byte,1,&n);
   if(byte==0xe9){DWORD protection=0;VirtualProtectEx(process,(void*)0x4125e8,10,0x40,&protection);
    WriteProcessMemory(process,(void*)0x4125e8,old,10,&n);FlushInstructionCache(process,(void*)0x4125e8,10);
    VirtualProtectEx(process,(void*)0x4125e8,10,protection,&protection);}
   unsigned char original[6]={0x83,0x78,0x08,0x01,0x75,0x65},existing[6];
   if(!ReadProcessMemory(process,(void*)0x4125ad,existing,6,&n))return 12;
   if(existing[0]!=0xe9){
    for(int i=0;i<6;++i)if(existing[i]!=original[i])return 12;
    void* code=VirtualAllocEx(process,0,64,0x3000,0x40);if(!code)return 7;
    unsigned char program[28]={0xf7,0x47,0x08,0x80,0x01,0,0,0x0f,0x85,0,0,0,0,
      0x83,0x78,0x08,0x01,0x0f,0x85,0,0,0,0,0xe9,0,0,0,0};
    *(DWORD*)(program+9)=0x412931-((DWORD)code+13);
    *(DWORD*)(program+19)=0x412618-((DWORD)code+23);
    *(DWORD*)(program+24)=0x4125b3-((DWORD)code+28);
    if(!WriteProcessMemory(process,code,program,sizeof(program),&n))return 8;
    FlushInstructionCache(process,code,sizeof(program));
    unsigned char hook[6]={0xe9,0,0,0,0,0x90};
    *(DWORD*)(hook+1)=(DWORD)code-(0x4125ad+5);
    DWORD protection=0;
    if(!VirtualProtectEx(process,(void*)0x4125ad,6,0x40,&protection))return 13;
    WriteProcessMemory(process,(void*)0x4125ad,hook,6,&n);FlushInstructionCache(process,(void*)0x4125ad,6);
    VirtualProtectEx(process,(void*)0x4125ad,6,protection,&protection);
   }
   return 0;
  }
  return 16;
 }
 DWORD editor=0;ReadProcessMemory(process,(void*)0x62f054,&editor,4,&n);if(!editor)return 17;
 DWORD eventValue=0,oldLine=0;
 if(!ReadProcessMemory(process,(void*)0x5ffe4c,&eventValue,4,&n))return 4;
 if(!ReadProcessMemory(process,(void*)0x6000dc,&oldLine,4,&n))return 5;
 HANDLE event=0;if(!DuplicateHandle(process,(HANDLE)eventValue,GetCurrentProcess(),&event,0,0,2))return 6;
 void* remote=VirtualAllocEx(process,0,512,0x3000,4);if(!remote){CloseHandle(event);return 7;}
 DWORD result=0,line=(DWORD)remote,key=13,current=line;
 if(!WriteProcessMemory(process,remote,command,length+1,&n))result=8;
 if(!result&&!WriteProcessMemory(process,(void*)0x6000dc,&line,4,&n))result=9;
 if(!result){
  WriteProcessMemory(process,(void*)0x6014c0,&key,4,&n);
  if(!SetEvent(event))result=10;
 }
 if(!result){
  for(int count=0;count<300;++count){Sleep(10);ReadProcessMemory(process,(void*)0x6000dc,&current,4,&n);if(current!=line)break;}
  if(current==line)result=11;
 }
 if(current==line)WriteProcessMemory(process,(void*)0x6000dc,&oldLine,4,&n);
 /* The console advances its input pointer before every parser has finished
    reading that line. Retain recent command buffers instead of freeing a
    string while the original interpreter may still reference it. */
 if(retiredPid!=pid){for(int i=0;i<16;++i)retiredCommands[i]=0;retiredIndex=0;retiredPid=pid;}
 if(retiredCommands[retiredIndex])VirtualFreeEx(process,retiredCommands[retiredIndex],0,0x8000);
 retiredCommands[retiredIndex]=remote;retiredIndex=(retiredIndex+1)%16;
 CloseHandle(event);return result;
}
void mainCRTStartup(void){
 GetModuleFileNameA(0,directory,1024);DWORD at=0,last=0;
 while(directory[at]){if(directory[at]=='\\'||directory[at]=='/')last=at;++at;}directory[last+1]=0;
 char* p=GetCommandLineA();if(*p=='"'){++p;while(*p&&*p!='"')++p;if(*p)++p;}else{while(*p&&*p!=' ')++p;}while(*p==' ')++p;
 if(p[0]=='-'&&p[1]=='-'){
  char filename[1100];path(filename,"control-request.bin");DWORD previous=0;
  for(;;){
   unsigned char request[264];DWORD bytes=0;
   HANDLE f=CreateFileA(filename,0x80000000,7,0,3,128,0);
   if(f!=(HANDLE)-1){ReadFile(f,request,sizeof(request),&bytes,0);CloseHandle(f);}
   if(bytes>=8){
    DWORD sequence=*(DWORD*)request,length=*(DWORD*)(request+4);
    if(sequence!=previous&&length<=253&&bytes==length+8){
     previous=sequence;
     if(length==5&&request[8]=='@'&&request[9]=='q'){report(0,sequence);ExitProcess(0);}
     report(execute((char*)request+8,length),sequence);
    }
   }
   Sleep(5);
  }
 }
 DWORD length=0;while(p[length])++length;DWORD code=execute(p,length);report(code,0);ExitProcess(code);
}
