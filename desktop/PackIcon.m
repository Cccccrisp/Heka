#import <Foundation/Foundation.h>
#import <libkern/OSByteOrder.h>

static void WriteU32(NSMutableData *data, uint32_t value) {
    uint32_t big = OSSwapHostToBigInt32(value);
    [data appendBytes:&big length:sizeof(big)];
}

static uint32_t FourCC(NSString *text) {
    const char *value = text.UTF8String;
    return ((uint32_t)value[0] << 24) | ((uint32_t)value[1] << 16) | ((uint32_t)value[2] << 8) | (uint32_t)value[3];
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 4 || (argc - 2) % 2 != 0) return 2;
        NSMutableArray<NSArray *> *chunks = [NSMutableArray array];
        NSUInteger total = 8;
        for (int index = 2; index < argc; index += 2) {
            NSString *tag = [NSString stringWithUTF8String:argv[index]];
            NSData *png = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[index + 1]]];
            if (tag.length != 4 || !png.length) return 1;
            [chunks addObject:@[tag, png]];
            total += 8 + png.length;
        }
        NSMutableData *icon = [NSMutableData dataWithCapacity:total];
        WriteU32(icon, FourCC(@"icns"));
        WriteU32(icon, (uint32_t)total);
        for (NSArray *chunk in chunks) {
            NSData *png = chunk[1];
            WriteU32(icon, FourCC(chunk[0]));
            WriteU32(icon, (uint32_t)(8 + png.length));
            [icon appendData:png];
        }
        return [icon writeToFile:[NSString stringWithUTF8String:argv[1]] atomically:YES] ? 0 : 1;
    }
}
