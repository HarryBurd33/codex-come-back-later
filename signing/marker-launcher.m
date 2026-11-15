// Owned launcher: selects reviewed state paths before executing the unchanged engine.
#import <AppKit/AppKit.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#include <libgen.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *configuration = __MARKER_CONFIG_C_STRING__;

static void fail(NSString *message) {
#ifdef MARKER_LAUNCHER_TEST
  fprintf(stderr, "%s\n", message.UTF8String);
#else
  [NSApplication sharedApplication];
  NSAlert *alert = [NSAlert new];
  alert.messageText = @"Codex Marker could not start";
  alert.informativeText = message;
  [alert addButtonWithTitle:@"OK"];
  [NSApp activateIgnoringOtherApps:YES];
  [alert runModal];
#endif
  exit(1);
}

static void directory(NSString *path, BOOL privateState, BOOL create) {
  if (create) {
    NSString *parent = path.stringByDeletingLastPathComponent;
    char resolved[PATH_MAX];
    if (!realpath(parent.fileSystemRepresentation,resolved) || strcmp(resolved,parent.fileSystemRepresentation))
      fail(@"The private state directory has an unexpected parent path.");
    if (mkdir(path.fileSystemRepresentation,0700) && errno != EEXIST)
      fail(@"The private state directory could not be created.");
  }
  struct stat value; char resolved[PATH_MAX];
  if (lstat(path.fileSystemRepresentation,&value) || !S_ISDIR(value.st_mode) ||
      value.st_uid != getuid() || (privateState && (value.st_mode & 0077)) ||
      !realpath(path.fileSystemRepresentation,resolved) || strcmp(resolved,path.fileSystemRepresentation))
    fail(@"A configured state directory is missing, linked, or has unexpected ownership or permissions.");
}

int main(int argc, char **argv) {
  @autoreleasepool {
    NSData *data = [NSData dataWithBytes:configuration length:strlen(configuration)];
    NSDictionary *config = [NSJSONSerialization JSONObjectWithData:data options:0 error:NULL];
    if (![config isKindOfClass:NSDictionary.class]) fail(@"Invalid launcher configuration.");
    NSDictionary *original = [NSDictionary dictionaryWithContentsOfFile:config[@"originalInfo"]];
    if (![original[@"CFBundleVersion"] isEqual:config[@"originalBuild"]] ||
        ![original[@"CFBundleShortVersionString"] isEqual:config[@"originalVersion"]])
      fail(@"The original Codex app has changed or is unavailable. Use the original app and request a marker compatibility review before continuing.");
    directory(config[@"sharedCodexHome"],NO,NO);
    NSString *root = config[@"root"];
    NSString *receipt = [root stringByAppendingPathComponent:@"isolation.json"];
    struct stat prior;
    if (!lstat(root.fileSystemRepresentation,&prior)) {
      directory(root,YES,NO);
      if (lstat(receipt.fileSystemRepresentation,&prior))
        fail(@"Existing private state has no matching ownership record. Preserve it and request a review.");
    } else if (errno!=ENOENT) fail(@"Could not inspect the private state directory.");
    directory(root,YES,YES);
    NSDictionary *paths = config[@"paths"];
    int descriptor = open(receipt.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if (descriptor >= 0) {
      size_t done=0;
      while (done<data.length) {
        ssize_t size=write(descriptor,(const char *)data.bytes+done,data.length-done);
        if (size<0 && errno==EINTR) continue;
        if (size<=0) { close(descriptor); fail(@"Could not save the private state record."); }
        done+=(size_t)size;
      }
      if (fsync(descriptor)) { close(descriptor); fail(@"Could not sync the private state record."); }
      close(descriptor);
    } else if (errno==EEXIST) {
      descriptor=open(receipt.fileSystemRepresentation,O_RDONLY|O_NOFOLLOW);
      struct stat value;
      if (descriptor<0 || fstat(descriptor,&value) || !S_ISREG(value.st_mode) ||
          value.st_uid!=getuid() || (value.st_mode&0077) || value.st_nlink!=1 ||
          value.st_size!=(off_t)data.length) fail(@"The private state record is unsafe or changed.");
      NSMutableData *saved=[NSMutableData dataWithLength:data.length];size_t done=0;
      while (done<data.length) {
        ssize_t size=read(descriptor,(char *)saved.mutableBytes+done,data.length-done);
        if (size<0 && errno==EINTR) continue;
        if (size<=0) { close(descriptor);fail(@"The private state record could not be read."); }
        done+=(size_t)size;
      }
      close(descriptor);
      if (![saved isEqual:data]) fail(@"The private state configuration changed. Preserve it and request a review.");
    } else fail(@"Could not open the private state record.");
    for (NSString *value in paths.allValues) {
      if (![value.stringByDeletingLastPathComponent isEqual:root]) fail(@"Private state path escaped its directory.");
      directory(value,YES,YES);
    }
    if (setenv("CODEX_HOME",[config[@"sharedCodexHome"] fileSystemRepresentation],1) ||
        setenv("CODEX_ELECTRON_USER_DATA_PATH",[paths[@"userData"] fileSystemRepresentation],1) ||
        setenv("CODEX_SPARKLE_ENABLED","false",1))
      fail(@"Could not configure the development app's state paths.");
    for (int i=1;i<argc;i++) {
      if (!strcmp(argv[i],"--") || !strncmp(argv[i],"--user-data-dir",strlen("--user-data-dir")))
        fail(@"Open Codex Marker normally without a custom user-data directory.");
    }
    char executable[PATH_MAX];
    if (!realpath(argv[0],executable)) fail(@"Could not locate the installed launcher.");
    NSString *engine=[[NSString stringWithUTF8String:dirname(executable)] stringByAppendingPathComponent:@"ChatGPT"];
    char **arguments=calloc((size_t)argc+2,sizeof(char *));
    if (!arguments) fail(@"Could not allocate launch arguments.");
    arguments[0]=(char *)engine.fileSystemRepresentation;
    for (int i=1;i<argc;i++) arguments[i]=argv[i];
    NSString *profile=[@"--user-data-dir=" stringByAppendingString:paths[@"userData"]];
    arguments[argc]=(char *)profile.UTF8String;
    execv(engine.fileSystemRepresentation,arguments);
    free(arguments);
    fail(@"The signed Codex engine could not start. Keep the original app and request a review.");
  }
  return 1;
}
