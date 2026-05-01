import AppKit
import Foundation

let outputPath = CommandLine.arguments.dropFirst().first

guard let outputPath else {
    fputs("usage: swift generate_app_icon.swift /path/to/output.png\n", stderr)
    exit(1)
}

let size = CGSize(width: 1024, height: 1024)
let image = NSImage(size: size)

image.lockFocus()

guard let context = NSGraphicsContext.current?.cgContext else {
    fputs("failed to acquire graphics context\n", stderr)
    exit(1)
}

let bounds = CGRect(origin: .zero, size: size)
let backgroundPath = NSBezierPath(
    roundedRect: bounds.insetBy(dx: 36, dy: 36),
    xRadius: 220,
    yRadius: 220
)
backgroundPath.addClip()

let colorSpace = CGColorSpaceCreateDeviceRGB()
let gradientColors = [
    NSColor(calibratedRed: 1.0, green: 0.56, blue: 0.58, alpha: 1.0).cgColor,
    NSColor(calibratedRed: 0.85, green: 0.16, blue: 0.20, alpha: 1.0).cgColor,
    NSColor(calibratedRed: 0.53, green: 0.05, blue: 0.08, alpha: 1.0).cgColor,
] as CFArray

let gradient = CGGradient(colorsSpace: colorSpace, colors: gradientColors, locations: [0.0, 0.56, 1.0])!
context.drawLinearGradient(
    gradient,
    start: CGPoint(x: 132, y: 92),
    end: CGPoint(x: 888, y: 940),
    options: []
)

NSColor.white.withAlphaComponent(0.06).setFill()
NSBezierPath(roundedRect: CGRect(x: 122, y: 736, width: 780, height: 166), xRadius: 44, yRadius: 44).fill()

context.saveGState()
context.setShadow(offset: CGSize(width: 0, height: -34), blur: 56, color: NSColor.black.withAlphaComponent(0.22).cgColor)
let coreRect = CGRect(x: 240, y: 220, width: 544, height: 544)
let corePath = NSBezierPath(roundedRect: coreRect, xRadius: 148, yRadius: 148)
let plateGradient = CGGradient(
    colorsSpace: colorSpace,
    colors: [
        NSColor.white.cgColor,
        NSColor(calibratedRed: 1.0, green: 0.94, blue: 0.94, alpha: 1.0).cgColor,
    ] as CFArray,
    locations: [0.0, 1.0]
)!
context.saveGState()
corePath.addClip()
context.drawLinearGradient(
    plateGradient,
    start: CGPoint(x: 512, y: 764),
    end: CGPoint(x: 512, y: 220),
    options: []
)
context.restoreGState()
NSColor.white.withAlphaComponent(0.55).setStroke()
corePath.lineWidth = 8
corePath.stroke()
context.restoreGState()

let monogram = NSMutableParagraphStyle()
monogram.alignment = .center

let attributes: [NSAttributedString.Key: Any] = [
    .font: NSFont.systemFont(ofSize: 272, weight: .bold),
    .foregroundColor: NSColor(calibratedRed: 0.78, green: 0.13, blue: 0.17, alpha: 1.0),
    .paragraphStyle: monogram,
]

context.saveGState()
context.setShadow(
    offset: CGSize(width: 0, height: -22),
    blur: 44,
    color: NSColor.black.withAlphaComponent(0.28).cgColor
)
let text = NSAttributedString(string: "{0}", attributes: attributes)
text.draw(in: CGRect(x: 120, y: 350, width: 784, height: 280))
context.restoreGState()

let accentBar = NSBezierPath(
    roundedRect: CGRect(x: 304, y: 270, width: 416, height: 28),
    xRadius: 14,
    yRadius: 14
)
NSColor(calibratedRed: 0.89, green: 0.24, blue: 0.27, alpha: 0.95).setFill()
accentBar.fill()

image.unlockFocus()

guard let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let png = bitmap.representation(using: .png, properties: [:]) else {
    fputs("failed to create PNG representation\n", stderr)
    exit(1)
}

let outputURL = URL(fileURLWithPath: outputPath)
try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
try png.write(to: outputURL)
