// Recovered exported ABI for Jianying 11.5.0 arm64. No bundled SDK/model.
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <stddef.h>
#include <math.h>
#include <dlfcn.h>
typedef struct {int sr,block;void *model;int len,channels;const char *json,*business;int buffers;const char *config;} Params;
typedef struct {uint32_t channels,samples;int interleave;float **data;} Buffer;
typedef struct {int type;uint32_t count;void *data,*context;} Block;
typedef struct {int type,id,writable;void *data;uint32_t size;const char *extra;void *context;} Property;
_Static_assert(offsetof(Params,buffers)==40,"params ABI");
_Static_assert(offsetof(Property,data)==16,"property ABI");
static void *load(const char *p,size_t *n){
 FILE *f=fopen(p,"rb");if(!f){perror(p);return NULL;}
 if(fseek(f,0,SEEK_END)){fclose(f);return NULL;}long size=ftell(f);
 if(size<=0){fclose(f);return NULL;}*n=(size_t)size;rewind(f);
 void *b=calloc(1,*n);if(!b||fread(b,1,*n,f)!=*n){free(b);b=NULL;}fclose(f);return b;
}
int main(int argc,char **argv){
 if(argc!=4){fprintf(stderr,"Usage: sami_align reference.f32 candidate.f32 result.json (16k mono equal length)\n");return 2;}
 size_t mn=0,an=0,bn=0;
 void *model=load("/Applications/VideoFusion-macOS.app/Contents/Resources/audiosami/time_align_freq_domain_v2.0.model",&mn);
 float *a=load(argv[1],&an),*b=load(argv[2],&bn);
 if(!model||!a||!b||an!=bn||an%4||an<32000*4||an>960000*4){fprintf(stderr,"Invalid input\n");return 2;}
 void *lib=dlopen("/Applications/VideoFusion-macOS.app/Contents/Frameworks/libsamicore.dylib",RTLD_NOW|RTLD_LOCAL);
 if(!lib){fprintf(stderr,"%s\n",dlerror());return 2;}
 int (*create)(void**,int,void*)=dlsym(lib,"SAMICoreCreateHandleByIdentify");
 int (*process)(void*,Block*,Block*)=dlsym(lib,"SAMICoreProcess");
 int (*get)(void*,int,Property*)=dlsym(lib,"SAMICoreGetPropertyById");
 int (*destroy)(void*)=dlsym(lib,"SAMICoreDestroyHandle");
 int (*dp)(Property*)=dlsym(lib,"SAMICoreDestroyProperty");
 if(!create||!process||!get||!destroy||!dp)return 2;
 Params p={16000,1024,model,(int)mn,1,NULL,NULL,2,NULL};void *h=NULL;Property result={0};
 int rc=create(&h,510,&p);fprintf(stderr,"create=%d\n",rc);if(rc||!h)return 3;
 float *ap[]={a},*bp[]={b};Buffer bufs[]={{1,0,0,ap},{1,0,0,bp}};
 Block in={50,2,bufs,NULL},out={0};size_t samples=an/4;
 for(size_t off=0;off<samples;off+=1024){
  size_t n=samples-off<1024?samples-off:1024;ap[0]=a+off;bp[0]=b+off;
  bufs[0].samples=bufs[1].samples=(uint32_t)n;rc=process(h,&in,&out);if(rc)break;
 }
 if(!rc)rc=get(h,2001,&result);
 if(!rc && (result.type!=459||result.size!=32||!result.data))rc=6;
 float delay=0;if(!rc){delay=((float*)result.data)[4];if(!isfinite(delay))rc=6;}
 int pr=result.data?dp(&result):0,dr=destroy(h);fprintf(stderr,"result=%d property_destroy=%d destroy=%d\n",rc,pr,dr);
 if(!rc&&(pr||dr))rc=7;
 if(!rc){FILE *f=fopen(argv[3],"wx");if(!f)return 2;
  if(fprintf(f,"{\"offset_ms\":%.9g,\"identify\":510,\"sample_rate\":16000}\n",delay)<0)rc=8;
  if(fclose(f))rc=8;
 }
 free(model);free(a);free(b);dlclose(lib);return rc?5:0;
}
