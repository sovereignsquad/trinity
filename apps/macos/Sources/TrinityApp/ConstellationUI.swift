import SwiftUI

enum TrinityPalette {
    static let canvas = Color(red: 0.96, green: 0.94, blue: 0.90)
    static let panel = Color.white.opacity(0.88)
    static let panelAlt = Color(red: 0.92, green: 0.88, blue: 0.82)
    static let border = Color(red: 0.84, green: 0.80, blue: 0.73)
    static let textPrimary = Color(red: 0.13, green: 0.11, blue: 0.08)
    static let textSecondary = Color(red: 0.37, green: 0.33, blue: 0.28)
    static let accent = Color(red: 0.72, green: 0.35, blue: 0.17)
    static let success = Color(red: 0.16, green: 0.48, blue: 0.28)
    static let warning = Color(red: 0.66, green: 0.42, blue: 0.0)
    static let info = Color(red: 0.17, green: 0.43, blue: 0.63)
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
