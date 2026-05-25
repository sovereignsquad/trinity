import AppKit
import SwiftUI

enum TrinityMetrics {
    static let pagePadding: CGFloat = 24
    static let sectionSpacing: CGFloat = 20
    static let panelSpacing: CGFloat = 14
    static let panelPadding: CGFloat = 18
    static let panelCornerRadius: CGFloat = 20
}

enum TrinityPalette {
    static let chrome = adaptiveTrinityColor(light: NSColor(red: 0.99, green: 0.96, blue: 0.95, alpha: 1), dark: NSColor(red: 0.08, green: 0.05, blue: 0.06, alpha: 1))
    static let canvas = adaptiveTrinityColor(light: NSColor(red: 0.97, green: 0.94, blue: 0.93, alpha: 1), dark: NSColor(red: 0.10, green: 0.08, blue: 0.09, alpha: 1))
    static let panel = adaptiveTrinityColor(light: NSColor.white.withAlphaComponent(0.93), dark: NSColor(red: 0.18, green: 0.12, blue: 0.13, alpha: 0.98))
    static let panelAlt = adaptiveTrinityColor(light: NSColor(red: 0.95, green: 0.88, blue: 0.87, alpha: 1), dark: NSColor(red: 0.23, green: 0.15, blue: 0.16, alpha: 1))
    static let border = adaptiveTrinityColor(light: NSColor(red: 0.88, green: 0.75, blue: 0.73, alpha: 1), dark: NSColor(red: 0.35, green: 0.22, blue: 0.23, alpha: 1))
    static let textPrimary = adaptiveTrinityColor(light: NSColor(red: 0.20, green: 0.08, blue: 0.09, alpha: 1), dark: NSColor(red: 0.97, green: 0.92, blue: 0.91, alpha: 1))
    static let textSecondary = adaptiveTrinityColor(light: NSColor(red: 0.44, green: 0.25, blue: 0.25, alpha: 1), dark: NSColor(red: 0.84, green: 0.73, blue: 0.72, alpha: 1))
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
                    TrinityPalette.chrome,
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
            .padding(TrinityMetrics.panelPadding)
            .background(
                RoundedRectangle(cornerRadius: TrinityMetrics.panelCornerRadius, style: .continuous)
                    .fill(TrinityPalette.panel)
            )
            .overlay(
                RoundedRectangle(cornerRadius: TrinityMetrics.panelCornerRadius, style: .continuous)
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

struct TrinitySectionHeader: View {
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.title3.weight(.semibold))
                .foregroundStyle(TrinityPalette.textPrimary)
            Text(subtitle)
                .foregroundStyle(TrinityPalette.textSecondary)
        }
    }
}

struct TrinityInlineBanner: View {
    let title: String
    let bodyText: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(color)
            Text(bodyText)
                .font(.subheadline)
                .foregroundStyle(TrinityPalette.textSecondary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.08))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(color.opacity(0.28), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

struct TrinityEmptyState: View {
    let title: String
    let bodyText: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
                .foregroundStyle(TrinityPalette.textPrimary)
            Text(bodyText)
                .foregroundStyle(TrinityPalette.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(TrinityPalette.panelAlt.opacity(0.55))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

struct TrinityLoadingState: View {
    let title: String

    var body: some View {
        HStack(spacing: 12) {
            ProgressView()
                .controlSize(.small)
            Text(title)
                .foregroundStyle(TrinityPalette.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(TrinityPalette.panelAlt.opacity(0.4))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

struct TrinityFormField<Control: View>: View {
    let label: String
    @ViewBuilder var control: Control

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(TrinityPalette.textPrimary)
            control
        }
    }
}

struct TrinityPathBadge: View {
    let label: String
    let path: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(TrinityPalette.textPrimary)
            Text(path)
                .font(.caption2)
                .foregroundStyle(TrinityPalette.textSecondary)
                .lineLimit(2)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(TrinityPalette.panelAlt.opacity(0.7))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}
