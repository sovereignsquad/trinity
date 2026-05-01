import AppKit
import SwiftUI

enum TrinityPalette {
    static let canvas = adaptiveTrinityColor(light: NSColor(red: 0.98, green: 0.94, blue: 0.93, alpha: 1), dark: NSColor(red: 0.11, green: 0.07, blue: 0.08, alpha: 1))
    static let panel = adaptiveTrinityColor(light: NSColor.white.withAlphaComponent(0.90), dark: NSColor(red: 0.17, green: 0.10, blue: 0.11, alpha: 0.96))
    static let panelAlt = adaptiveTrinityColor(light: NSColor(red: 0.95, green: 0.87, blue: 0.86, alpha: 1), dark: NSColor(red: 0.22, green: 0.13, blue: 0.14, alpha: 1))
    static let border = adaptiveTrinityColor(light: NSColor(red: 0.89, green: 0.74, blue: 0.72, alpha: 1), dark: NSColor(red: 0.33, green: 0.19, blue: 0.20, alpha: 1))
    static let textPrimary = adaptiveTrinityColor(light: NSColor(red: 0.22, green: 0.08, blue: 0.09, alpha: 1), dark: NSColor(red: 0.98, green: 0.92, blue: 0.91, alpha: 1))
    static let textSecondary = adaptiveTrinityColor(light: NSColor(red: 0.47, green: 0.26, blue: 0.26, alpha: 1), dark: NSColor(red: 0.85, green: 0.72, blue: 0.71, alpha: 1))
    static let accent = adaptiveTrinityColor(light: NSColor(red: 0.77, green: 0.17, blue: 0.19, alpha: 1), dark: NSColor(red: 0.93, green: 0.32, blue: 0.34, alpha: 1))
    static let success = adaptiveTrinityColor(light: NSColor(red: 0.16, green: 0.48, blue: 0.28, alpha: 1), dark: NSColor(red: 0.31, green: 0.77, blue: 0.48, alpha: 1))
    static let warning = adaptiveTrinityColor(light: NSColor(red: 0.66, green: 0.42, blue: 0.0, alpha: 1), dark: NSColor(red: 0.88, green: 0.63, blue: 0.20, alpha: 1))
    static let info = adaptiveTrinityColor(light: NSColor(red: 0.55, green: 0.22, blue: 0.24, alpha: 1), dark: NSColor(red: 0.95, green: 0.57, blue: 0.58, alpha: 1))
}

private func adaptiveTrinityColor(light: NSColor, dark: NSColor) -> Color {
    Color(
        nsColor: NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light
        }
    )
}

struct TrinityShell<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 1.0, green: 0.98, blue: 0.95),
                    TrinityPalette.canvas
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .overlay(
                RadialGradient(
                    colors: [TrinityPalette.accent.opacity(0.14), .clear],
                    center: .topLeading,
                    startRadius: 20,
                    endRadius: 360
                )
            )
            .ignoresSafeArea()

            content
        }
        .tint(TrinityPalette.accent)
    }
}

struct TrinityPanelModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(18)
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(TrinityPalette.panel)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(TrinityPalette.border, lineWidth: 1)
            )
            .shadow(color: Color.black.opacity(0.08), radius: 18, x: 0, y: 12)
    }
}

extension View {
    func trinityPanel() -> some View {
        modifier(TrinityPanelModifier())
    }
}

struct TrinityStatusPill: View {
    let label: String
    let color: Color

    var body: some View {
        Text(label)
            .font(.caption.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(color.opacity(0.12))
            .clipShape(Capsule())
    }
}
