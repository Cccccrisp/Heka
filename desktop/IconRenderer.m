#import <Cocoa/Cocoa.h>

static NSColor *Color(CGFloat red, CGFloat green, CGFloat blue) {
    return [NSColor colorWithSRGBRed:red / 255.0 green:green / 255.0 blue:blue / 255.0 alpha:1.0];
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc != 3) return 2;
        NSInteger size = [[NSString stringWithUTF8String:argv[2]] integerValue];
        if (size < 16) return 2;
        CGFloat scale = size / 1024.0;
        NSImage *image = [[NSImage alloc] initWithSize:NSMakeSize(size, size)];
        [image lockFocus];
        [Color(248, 247, 244) setFill];
        [[NSBezierPath bezierPathWithRoundedRect:NSMakeRect(0, 0, size, size) xRadius:226 * scale yRadius:226 * scale] fill];
        NSBezierPath *border = [NSBezierPath bezierPathWithRoundedRect:NSMakeRect(34 * scale, 34 * scale, 956 * scale, 956 * scale) xRadius:198 * scale yRadius:198 * scale];
        border.lineWidth = 8 * scale;
        [Color(215, 196, 158) setStroke];
        [border stroke];
        CGContextRef context = [[NSGraphicsContext currentContext] CGContext];
        CGContextSetLineCap(context, kCGLineCapSquare);
        CGContextSetLineJoin(context, kCGLineJoinMiter);
        CGContextSetStrokeColorWithColor(context, Color(32, 34, 35).CGColor);
        CGContextSetLineWidth(context, 72 * scale);
        CGContextBeginPath(context);
        CGContextMoveToPoint(context, 234 * scale, 300 * scale); CGContextAddLineToPoint(context, 234 * scale, 724 * scale);
        CGContextMoveToPoint(context, 510 * scale, 300 * scale); CGContextAddLineToPoint(context, 510 * scale, 724 * scale);
        CGContextMoveToPoint(context, 234 * scale, 512 * scale); CGContextAddLineToPoint(context, 510 * scale, 512 * scale);
        CGContextStrokePath(context);
        CGContextSetStrokeColorWithColor(context, Color(183, 138, 67).CGColor);
        CGContextBeginPath(context);
        CGContextMoveToPoint(context, 783 * scale, 326 * scale); CGContextAddLineToPoint(context, 582 * scale, 512 * scale); CGContextAddLineToPoint(context, 783 * scale, 698 * scale);
        CGContextStrokePath(context);
        [image unlockFocus];
        NSBitmapImageRep *bitmap = [[NSBitmapImageRep alloc] initWithData:image.TIFFRepresentation];
        NSData *png = [bitmap representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
        return [png writeToFile:[NSString stringWithUTF8String:argv[1]] atomically:YES] ? 0 : 1;
    }
}
