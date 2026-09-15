import AppKit
import Foundation

guard CommandLine.arguments.count == 2 else {
    fputs("usage: generate_icon.swift OUTPUT.png\n", stderr)
    exit(2)
}

let size = NSSize(width: 1024, height: 1024)
let image = NSImage(size: size)
image.lockFocus()

NSColor(calibratedRed: 0.035, green: 0.035, blue: 0.060, alpha: 1).setFill()
NSBezierPath(roundedRect: NSRect(origin: .zero, size: size), xRadius: 220, yRadius: 220).fill()

let context = NSGraphicsContext.current
context?.saveGraphicsState()
let transform = NSAffineTransform()
transform.translateX(by: 512, yBy: 512)
transform.rotate(byDegrees: 10)
transform.translateX(by: -512, yBy: -512)
transform.concat()

let purple = NSColor(calibratedRed: 0.55, green: 0.48, blue: 0.98, alpha: 1)
purple.setStroke()
for y in [650.0, 456.0, 262.0] {
    let path = NSBezierPath(roundedRect: NSRect(x: 310, y: y, width: 404, height: 126), xRadius: 30, yRadius: 30)
    path.lineWidth = 34
    path.stroke()
}
context?.restoreGraphicsState()
image.unlockFocus()

guard let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fputs("could not render the DSH Forge icon\n", stderr)
    exit(1)
}
try png.write(to: URL(fileURLWithPath: CommandLine.arguments[1]), options: .atomic)
