/* GOG 1.22L editor controller. Original rendering is unmodified.
 * Executable SHA256 is checked by retail.py before starting this helper. */
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
 DWORD s[18]={0x41544c53,code,0,0,0,0,0,0,0,0,sequence,0,0,0,0,0,0,0},n=0;
 if(observed){
  ReadProcessMemory(observed,(void*)0x666970,s+2,4,&n);
  ReadProcessMemory(observed,(void*)0x66697c,s+3,12,&n);
  ReadProcessMemory(observed,(void*)0x666950,s+6,8,&n);
  ReadProcessMemory(observed,(void*)0x668154,s+8,4,&n);
  DWORD sites[4]={0x456d9d,0x456fb8,0x45737e,0x413a15};int hidden=1;
  for(int i=0;i<4;++i){unsigned short guard=0;ReadProcessMemory(observed,(void*)sites[i],&guard,2,&n);if(guard!=0xe990)hidden=0;}
  s[9]=hidden?0xe9eb:0;

  ReadProcessMemory(observed,(void*)0x5d7a18,s+11,4,&n);
  DWORD screen=0;ReadProcessMemory(observed,(void*)0x667fd0,&screen,4,&n);
  s[17]=screen;
  if(screen){ReadProcessMemory(observed,(void*)(screen+0x48),s+12,4,&n);ReadProcessMemory(observed,(void*)(screen+0x690),s+13,4,&n);}
  ReadProcessMemory(observed,(void*)0x6671a4,s+14,4,&n);
  ReadProcessMemory(observed,(void*)0x6671a8,s+15,4,&n);
  ReadProcessMemory(observed,(void*)0x6671c0,s+16,4,&n);
 }
 output("control-state.bin",s,sizeof(s));
}
static DWORD execute(const char* text,DWORD length){
 char command[256];if(length>253)return 16;
 for(DWORD i=0;i<length;++i)command[i]=text[i];command[length++]=10;command[length]=0;
 if(observed){CloseHandle(observed);observed=0;}
 HWND h=FindWindowA(0,"Revenant");if(!h)return 2;
 DWORD pid=0,n=0;GetWindowThreadProcessId(h,&pid);
 HANDLE process=OpenProcess(0x478,0,pid);if(!process)return 3;observed=process;
 unsigned char signature[2];
 if(!ReadProcessMemory(process,(void*)0x43f52a,signature,2,&n)||n!=2||signature[0]!=0xff||signature[1]!=0xd7)return 15;
 if(command[0]=='@'){
  if(command[1]=='i')return 0;
  if(command[1]=='e'){SendMessageA(h,0x100,123,1);SendMessageA(h,0x101,123,1);Sleep(80);return 0;}
  if(command[1]=='h'){
   /* Apply retail's normal OF_EDITOR filter in the editor's 2D draws.
      Native light emission remains active; only helper imagery is omitted. */
   DWORD sites[4]={0x456d9d,0x456fb8,0x45737e,0x413a15};unsigned char tails[4][4]={{0xb0,1,0,0},{0xac,1,0,0},{0x9f,1,0,0},{0x71,5,0,0}};
   for(int i=0;i<4;++i){unsigned char b[6];if(!ReadProcessMemory(process,(void*)sites[i],b,6,&n)||n!=6)return 18;
    if(!((b[0]==0x0f&&b[1]==0x84)||(b[0]==0x90&&b[1]==0xe9)))return 12;
    for(int j=0;j<4;++j)if(b[j+2]!=tails[i][j])return 12;
    DWORD protection;unsigned char jump[2]={0x90,0xe9};VirtualProtectEx(process,(void*)sites[i],6,0x40,&protection);WriteProcessMemory(process,(void*)sites[i],jump,2,&n);FlushInstructionCache(process,(void*)sites[i],6);VirtualProtectEx(process,(void*)sites[i],6,protection,&protection);
   }
   return 0;
  }
  if(command[1]=='p'){
   DWORD pause=0;WriteProcessMemory(process,(void*)0x5d7a20,&pause,4,&n);
   /* Disable only editor edge panning; preserve the original world renderer. */
   DWORD sites[2]={0x4505d2,0x4505e3};
   for(int i=0;i<2;++i){
    unsigned char bytes[6];if(!ReadProcessMemory(process,(void*)sites[i],bytes,6,&n)||n!=6)return 18;
    if(bytes[0]!=0x89||(bytes[1]!=0x86&&bytes[1]!=0xae)||bytes[2]!=(i?0x18:0x14)||bytes[3]!=1||bytes[4]||bytes[5])return 12;
    DWORD protection;unsigned char zero=0xae;VirtualProtectEx(process,(void*)sites[i],6,0x40,&protection);WriteProcessMemory(process,(void*)(sites[i]+1),&zero,1,&n);FlushInstructionCache(process,(void*)sites[i],6);VirtualProtectEx(process,(void*)sites[i],6,protection,&protection);
   }
   DWORD cursor[2]={0x43a480,0x43a5a0};unsigned char first[2]={0x8b,0xa1},ret=0xc3;
   for(int i=0;i<2;++i){unsigned char b=0;ReadProcessMemory(process,(void*)cursor[i],&b,1,&n);if(b!=first[i]&&b!=ret)return 12;DWORD protection;VirtualProtectEx(process,(void*)cursor[i],1,0x40,&protection);WriteProcessMemory(process,(void*)cursor[i],&ret,1,&n);FlushInstructionCache(process,(void*)cursor[i],1);VirtualProtectEx(process,(void*)cursor[i],1,protection,&protection);}
   DWORD zeros[2]={0,0};WriteProcessMemory(process,(void*)0x6669ec,zeros,8,&n);return 0;
  }
  if(command[1]=='w'){
   DWORD screen=0,first=0,current=0;ReadProcessMemory(process,(void*)0x667fd0,&screen,4,&n);if(!screen)return 18;
   ReadProcessMemory(process,(void*)(screen+0x48),&first,4,&n);
   DWORD quiet=0xffffffff;
   for(int i=0;i<2400;++i){
    Sleep(5);ReadProcessMemory(process,(void*)(screen+0x48),&current,4,&n);
    DWORD busy=0,rects=0,queued=0,transition=0;
    /* Retail UpdateLoop/FlushUpdate/PutQueueRectsToDisplay and MapPane::Pulse. */
    if(!ReadProcessMemory(process,(void*)0x658324,&busy,4,&n)||!ReadProcessMemory(process,(void*)0x658438,&rects,4,&n)||
       !ReadProcessMemory(process,(void*)0x66710c,&queued,4,&n)||!ReadProcessMemory(process,(void*)0x6671d0,&transition,4,&n))return 18;
    if(busy||rects||queued||transition){quiet=0xffffffff;continue;}
    if(quiet==0xffffffff)quiet=current;
    if(current-first>=8&&current-quiet>=2)return 0;
   }return 19;
  }
  if(command[1]=='g'||command[1]=='d'){DWORD grid=command[1]=='g';WriteProcessMemory(process,(void*)0x5d7a18,&grid,4,&n);return 0;}
  if(command[1]=='t'){
   DWORD minute=0;for(DWORD i=6;i+1<length;++i){if(command[i]<'0'||command[i]>'9')return 16;minute=minute*10+command[i]-'0';}
   if(minute>1439)return 16;DWORD screen=0,vt=0;ReadProcessMemory(process,(void*)0x667fd0,&screen,4,&n);ReadProcessMemory(process,(void*)screen,&vt,4,&n);
   if(vt!=0x5a5320)return 17;
   WriteProcessMemory(process,(void*)(screen+0x690),&minute,4,&n);return 0;
  }
  if(command[1]=='m'){
   DWORD address=0,size=0,at=8;
   while(command[at]&&command[at]!=' '){char c=command[at++];DWORD digit=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:99;if(digit>15)return 16;address=address*16+digit;}
   ++at;while(command[at]>='0'&&command[at]<='9')size=size*10+command[at++]-'0';
   if(!size||size>65536)return 16;static char bytes[65536];if(!ReadProcessMemory(process,(void*)address,bytes,size,&n)||n!=size)return 18;output("control-memory.bin",bytes,size);return 0;
  }
  return 16;
 }
 DWORD editor=0;ReadProcessMemory(process,(void*)0x668154,&editor,4,&n);if(!editor)return 17;
 DWORD eventValue=0,oldLine=0;ReadProcessMemory(process,(void*)0x656b24,&eventValue,4,&n);ReadProcessMemory(process,(void*)0x656db4,&oldLine,4,&n);
 HANDLE event=0;if(!DuplicateHandle(process,(HANDLE)eventValue,GetCurrentProcess(),&event,0,0,2))return 6;
 void* remote=VirtualAllocEx(process,0,512,0x3000,4);if(!remote){CloseHandle(event);return 7;}
 DWORD line=(DWORD)remote,key=13,current=line;
 if(!WriteProcessMemory(process,remote,command,length+1,&n))return 8;
 WriteProcessMemory(process,(void*)0x656db4,&line,4,&n);WriteProcessMemory(process,(void*)0x6581b8,&key,4,&n);SetEvent(event);
 for(int count=0;count<300;++count){Sleep(10);ReadProcessMemory(process,(void*)0x656db4,&current,4,&n);if(current!=line)break;}
 if(current==line)WriteProcessMemory(process,(void*)0x656db4,&oldLine,4,&n);
 if(retiredPid!=pid){for(int i=0;i<16;++i)retiredCommands[i]=0;retiredIndex=0;retiredPid=pid;}
 if(retiredCommands[retiredIndex])VirtualFreeEx(process,retiredCommands[retiredIndex],0,0x8000);
 retiredCommands[retiredIndex]=remote;retiredIndex=(retiredIndex+1)%16;CloseHandle(event);return current==line?11:0;
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
