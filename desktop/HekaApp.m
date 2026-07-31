#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>

@interface HekaAppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) WKWebView *webView;
@property(nonatomic, strong) NSTask *server;
@property(nonatomic, strong) NSPipe *outputPipe;
@end

@implementation HekaAppDelegate

- (NSURL *)logURL {
    NSURL *support = [[[NSFileManager defaultManager] URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask] firstObject];
    return [[support URLByAppendingPathComponent:@"Heka" isDirectory:YES] URLByAppendingPathComponent:@"desktop-launcher.log"];
}

- (void)log:(NSString *)message {
    NSURL *url = [self logURL];
    [[NSFileManager defaultManager] createDirectoryAtURL:[url URLByDeletingLastPathComponent] withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *line = [NSString stringWithFormat:@"[%@] %@\n", [NSDate date], message];
    if ([[NSFileManager defaultManager] fileExistsAtPath:url.path]) {
        NSFileHandle *handle = [NSFileHandle fileHandleForWritingAtPath:url.path];
        [handle seekToEndOfFile];
        [handle writeData:[line dataUsingEncoding:NSUTF8StringEncoding]];
        [handle closeFile];
    } else {
        [line writeToURL:url atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 1320, 860)
                                               styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
                                                 backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"Heka";
    [self.window center];
    self.webView = [[WKWebView alloc] initWithFrame:self.window.contentView.bounds];
    self.webView.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    self.window.contentView = self.webView;
    [self.window makeKeyAndOrderFront:nil];
    [self startServer];
}

- (void)startServer {
    [self log:@"Launching native desktop shell"];
    NSURL *resources = [[NSBundle mainBundle] resourceURL];
    NSURL *project = [resources URLByAppendingPathComponent:@"heka" isDirectory:YES];
    NSURL *support = [[[[NSFileManager defaultManager] URLsForDirectory:NSApplicationSupportDirectory inDomains:NSUserDomainMask] firstObject] URLByAppendingPathComponent:@"Heka" isDirectory:YES];
    [[NSFileManager defaultManager] createDirectoryAtURL:support withIntermediateDirectories:YES attributes:nil error:nil];
    NSMutableDictionary *environment = [[[NSProcessInfo processInfo] environment] mutableCopy];
    environment[@"HEKA_PORT"] = @"0";
    environment[@"HEKA_OPEN_BROWSER"] = @"0";
    environment[@"HEKA_DATA_DIR"] = support.path;
    environment[@"HEKA_CONFIG_FILE"] = [[support URLByAppendingPathComponent:@".env"] path];
    self.server = [[NSTask alloc] init];
    self.server.launchPath = @"/usr/bin/env";
    self.server.arguments = @[@"python3", @"server.py"];
    self.server.currentDirectoryURL = project;
    self.server.environment = environment;
    self.outputPipe = [NSPipe pipe];
    self.server.standardOutput = self.outputPipe;
    self.server.standardError = self.outputPipe;
    __weak typeof(self) weakSelf = self;
    self.outputPipe.fileHandleForReading.readabilityHandler = ^(NSFileHandle *handle) {
        NSData *data = handle.availableData;
        NSString *text = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
        if (!text.length) return;
        [weakSelf log:[NSString stringWithFormat:@"server: %@", [text stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]]]];
        for (NSString *line in [text componentsSeparatedByString:@"\n"]) {
            if ([line hasPrefix:@"HEKA_READY="]) {
                NSString *address = [line substringFromIndex:@"HEKA_READY=".length];
                dispatch_async(dispatch_get_main_queue(), ^{
                    NSURL *url = [NSURL URLWithString:address];
                    if (url) [weakSelf.webView loadRequest:[NSURLRequest requestWithURL:url]];
                });
            }
        }
    };
    @try { [self.server launch]; }
    @catch (NSException *exception) { [self showError:@"Heka 没能启动。请确认 Mac 已安装 Python 3。"]; }
}

- (void)showError:(NSString *)message {
    NSString *page = [NSString stringWithFormat:@"<main style='font:18px -apple-system;padding:48px;color:#202223'><h1>Heka 无法启动</h1><p>%@</p></main>", message];
    [self.webView loadHTMLString:page baseURL:nil];
}

- (void)applicationWillTerminate:(NSNotification *)notification { [self.server terminate]; }
@end

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        HekaAppDelegate *delegate = [[HekaAppDelegate alloc] init];
        app.delegate = delegate;
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        [app activateIgnoringOtherApps:YES];
        [app run];
    }
    return 0;
}
