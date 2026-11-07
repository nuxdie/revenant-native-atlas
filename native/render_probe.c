typedef void* HANDLE;typedef void* HWND;typedef unsigned long DWORD;
#define API __declspec(dllimport) __stdcall
API HWND FindWindowA(const char*,const char*);
API DWORD GetWindowThreadProcessId(HWND,DWORD*);
API DWORD GetModuleFileNameA(HANDLE,char*,DWORD);
API HANDLE OpenProcess(DWORD,int,DWORD);
API HANDLE OpenThread(DWORD,int,DWORD);
API DWORD SuspendThread(HANDLE);API DWORD ResumeThread(HANDLE);
API int ReadProcessMemory(HANDLE,const void*,void*,DWORD,DWORD*);
API int WriteProcessMemory(HANDLE,void*,const void*,DWORD,DWORD*);
API void* VirtualAllocEx(HANDLE,void*,DWORD,DWORD,DWORD);
API int VirtualProtectEx(HANDLE,void*,DWORD,DWORD,DWORD*);
API int FlushInstructionCache(HANDLE,const void*,DWORD);
API HANDLE CreateFileA(const char*,DWORD,DWORD,void*,DWORD,DWORD,HANDLE);
API int ReadFile(HANDLE,void*,DWORD,DWORD*,void*);API int WriteFile(HANDLE,const void*,DWORD,DWORD*,void*);
API int CloseHandle(HANDLE);API void Sleep(DWORD);API void ExitProcess(unsigned);
static char folder[1024],file[1100];static unsigned char code[4096],trace[16+65536*16];
static void path(const char*name){int i=0,j=0;while(folder[i]){file[i]=folder[i];i++;}while(name[j])file[i++]=name[j++];file[i]=0;}
void mainCRTStartup(){
 DWORD n=0,pid=0;HWND window=FindWindowA(0,"Revenant");if(!window)ExitProcess(2);
 DWORD tid=GetWindowThreadProcessId(window,&pid);HANDLE process=OpenProcess(0x478,0,pid);if(!process)ExitProcess(3);
 unsigned char signature[6],expected[6]={0xa1,0xec,0x38,0x58,0,0x56};
 if(!ReadProcessMemory(process,(void*)0x415760,signature,6,&n)||n!=6)ExitProcess(4);
 for(int i=0;i<6;i++)if(signature[i]!=expected[i])ExitProcess(5);
 GetModuleFileNameA(0,folder,1024);int last=0;for(int i=0;folder[i];i++)if(folder[i]=='\\')last=i+1;folder[last]=0;
 path("render-state-code.bin");HANDLE input=CreateFileA(file,0x80000000,7,0,3,128,0);DWORD length=0;
 if(input==(HANDLE)-1||!ReadFile(input,code,4096,&length,0)||!length||length>=4096)ExitProcess(6);CloseHandle(input);
 void* allocation=VirtualAllocEx(process,0,sizeof(trace)+8192,0x3000,0x40);if(!allocation)ExitProcess(7);
 for(DWORD i=0;i+4<=length;i++)if(*(DWORD*)(code+i)==0x77770000){*(DWORD*)(code+i)=(DWORD)allocation;i+=3;}
 void* target=(char*)allocation+sizeof(trace)+64;if(!WriteProcessMemory(process,target,code,length,&n))ExitProcess(8);
 FlushInstructionCache(process,target,length);HANDLE thread=OpenThread(2,0,tid);if(!thread)ExitProcess(9);
 unsigned char hook[6]={0xe9,0,0,0,0,0x90};*(DWORD*)(hook+1)=(DWORD)target-0x415765;
 DWORD old=0;SuspendThread(thread);VirtualProtectEx(process,(void*)0x415760,6,0x40,&old);
 int written=WriteProcessMemory(process,(void*)0x415760,hook,6,&n);FlushInstructionCache(process,(void*)0x415760,6);
 VirtualProtectEx(process,(void*)0x415760,6,old,&old);ResumeThread(thread);if(!written)ExitProcess(10);
 Sleep(5000);
 SuspendThread(thread);VirtualProtectEx(process,(void*)0x415760,6,0x40,&old);
 WriteProcessMemory(process,(void*)0x415760,expected,6,&n);FlushInstructionCache(process,(void*)0x415760,6);
 VirtualProtectEx(process,(void*)0x415760,6,old,&old);ResumeThread(thread);
 if(!ReadProcessMemory(process,allocation,trace,sizeof(trace),&n)||n!=sizeof(trace))ExitProcess(11);
 path("render-state-trace.bin");HANDLE output=CreateFileA(file,0x40000000,7,0,2,128,0);
 WriteFile(output,trace,sizeof(trace),&n,0);CloseHandle(output);CloseHandle(thread);CloseHandle(process);ExitProcess(0);
}
