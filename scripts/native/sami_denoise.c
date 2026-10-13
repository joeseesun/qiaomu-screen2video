// ABI observed in Jianying 11.5.0 / SAMI mac_14.91.5-mtcc, arm64.
// Loads the user's original library; no patches or private C++ entrypoints.
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>
#include <time.h>
typedef struct { int sampleRate, maxBlockSize; void *modelBuffer; int modelLen, numChannel; char reserved[64]; } CreateParams;
typedef struct { uint32_t numberChannels, numberSamples; int isInterleave; float **data; } AudioBuffer;
typedef struct { int dataType; uint32_t numberAudioData; void *audioData, *userContext; } AudioBlock;
_Static_assert(offsetof(AudioBuffer,data)==16,"audio ABI");
_Static_assert(offsetof(CreateParams,numChannel)==20,"parameter ABI");
int main(int argc,char **argv) {
 if(argc!=3){fprintf(stderr,"Usage: %s input.f32 output.f32 (mono 44100, includes padded tail)\n",argv[0]);return 2;}
 FILE *in=fopen(argv[1],"rb");if(!in){perror("input");return 2;}
 FILE *out=fopen(argv[2],"wbx");if(!out){perror("output");return 2;}
 void *lib=dlopen("/Applications/VideoFusion-macOS.app/Contents/Frameworks/libsamicore.dylib",RTLD_NOW|RTLD_LOCAL);
 if(!lib){fprintf(stderr,"%s\n",dlerror());return 1;}
 int (*create)(void**,int,void*)=dlsym(lib,"SAMICoreCreateHandleByIdentify");
 int (*destroy)(void*)=dlsym(lib,"SAMICoreDestroyHandle");
 int (*process)(void*,AudioBlock*,AudioBlock*)=dlsym(lib,"SAMICoreProcess");
 if(!create||!destroy||!process)return 1;
 FILE *mf=fopen("/Applications/VideoFusion-macOS.app/Contents/Resources/audiosami/unet_denoise_44k_music_model_v1.0.model","rb");
 if(!mf)return 2;fseek(mf,0,SEEK_END);long n=ftell(mf);rewind(mf);void *model=malloc(n);if(!model||fread(model,1,n,mf)!=n)return 2;fclose(mf);
 CreateParams p={.sampleRate=44100,.maxBlockSize=512,.modelBuffer=model,.modelLen=(int)n,.numChannel=1};
 void *h=NULL;int rc=create(&h,308,&p);fprintf(stderr,"create status=%d\n",rc);if(rc||!h)return 3;
 float src[512],dst[512];float *ip[]={src},*op[]={dst};
 AudioBuffer ib={1,512,0,ip},ob={1,512,0,op};AudioBlock bi={50,1,&ib,NULL},bo={50,1,&ob,NULL};
 size_t blocks=0,actual=0;int eof=0,flush=0;clock_t start=clock();
 while(1){
  memset(src,0,sizeof(src));size_t got=eof?0:fread(src,sizeof(float),512,in);actual+=got;
  if(ferror(in)){rc=4;break;}if(got<512)eof=1;
  // Two seconds of zero input drain algorithm latency; Python trims after alignment.
  if(eof&&flush++>=173)break;
  for(int j=0;j<512;j++)dst[j]=NAN;
  ib.numberSamples=ob.numberSamples=512;
  rc=process(h,&bi,&bo);if(rc){fprintf(stderr,"process block=%zu status=%d\n",blocks,rc);break;}
  if(ob.numberSamples!=512){fprintf(stderr,"unexpected sample count=%u\n",ob.numberSamples);rc=4;break;}
  for(int j=0;j<512;j++)if(!isfinite(dst[j])){fprintf(stderr,"invalid sample block=%zu\n",blocks);rc=4;break;}
  if(rc)break;if(fwrite(dst,sizeof(float),512,out)!=512){rc=4;break;}blocks++;
 }
 fprintf(stderr,"process status=%d blocks=%zu input_samples=%zu output_samples=%zu cpu_seconds=%.4f\n",rc,blocks,actual,blocks*512,(double)(clock()-start)/CLOCKS_PER_SEC);
 int dr=destroy(h);fprintf(stderr,"destroy status=%d\n",dr);fclose(in);fclose(out);free(model);return rc?5:dr;
}
